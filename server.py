import os
import uuid
import base64
import binascii
import subprocess
import time
from typing import Optional

from fastapi import (
    FastAPI,
    Request,
    Query,
    File,
    UploadFile,
    HTTPException,
    Depends,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration - can be customized via .env file
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "png,jpg,jpeg,bmp").split(","))
PRINT_SCRIPT = os.getenv("PRINT_SCRIPT") or os.path.join(os.path.dirname(__file__), "print_image_any.py")
MAX_WIDTH_DEFAULT = os.getenv("MAX_WIDTH_DEFAULT", "576")
MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20")) * 1024 * 1024
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "3006"))

app = FastAPI()

# CORS configuration - allow all origins like Flask-CORS default
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def json_error(message: str, status: int = 400, **extra):
    payload = {"error": message}
    if extra:
        payload.update(extra)
    return JSONResponse(content=payload, status_code=status)


def is_allowed_file(filename: str) -> bool:
    return "." in filename and (
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def require_printer(
    printer: Optional[str] = Query(None, alias="printer"),
    p: Optional[str] = Query(None, alias="p"),
    verify: Optional[str] = Query(None),
):
    printer_name = printer or p
    if not printer_name:
        raise HTTPException(
            status_code=400,
            detail={"error": "Missing 'printer' query parameter (alias: p)."}
        )
    
    if verify and verify.strip() in {"1", "true", "yes"}:
        try:
            subprocess.run(
                ["lpstat", "-p", printer_name],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Printer not found or not enabled.",
                    "stderr": e.stderr.decode("utf-8", "ignore"),
                }
            )
    
    return printer_name


def send_raw(printer: str, data: bytes):
    return subprocess.run(
        ["lp", "-d", printer, "-o", "raw"],
        input=data,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def send_image_file(printer: str, filepath: str):
    """Send image file through CUPS processing (uses PPD settings)"""
    return subprocess.run(
        ["lp", "-d", printer, filepath],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def printer_has_ppd(printer: str) -> bool:
    """Check if printer has a PPD file (supports hardware options)"""
    result = subprocess.run(
        ["lpoptions", "-p", printer, "-l"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0 and b"Unable to get PPD" not in result.stderr


def clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


def get_bool_arg(request: Request, name: str, default: bool = False) -> bool:
    v = request.query_params.get(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in {"1", "true", "yes", "on"}


async def get_json_or_form(request: Request, key: str) -> Optional[str]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            js = await request.json()
            return js.get(key)
        except:
            return None
    else:
        form = await request.form()
        return form.get(key)


def esc_init() -> bytes:
    return b"\x1b\x40"


def esc_align(align: str) -> bytes:
    m = {"left": 0, "center": 1, "right": 2}.get(align, 0)
    return bytes([0x1B, 0x61, m])


def esc_bold(on: bool) -> bytes:
    return bytes([0x1B, 0x45, 1 if on else 0])


def esc_underline(mode: str) -> bytes:
    m = {"none": 0, "single": 1, "double": 2}.get(mode, 0)
    return bytes([0x1B, 0x2D, m])


def esc_size(width: int = 1, height: int = 1) -> bytes:
    w = clamp(width, 1, 8) - 1
    h = clamp(height, 1, 8) - 1
    n = (w << 4) | h
    return bytes([0x1D, 0x21, n])


def esc_feed(lines: int = 1) -> bytes:
    n = clamp(int(lines), 0, 255)
    return bytes([0x1B, 0x64, n])


def esc_cut(mode: str = "partial", feed: int = 3) -> bytes:
    out = bytearray()
    if feed:
        out += esc_feed(feed)
    if mode == "full":
        out += b"\x1d\x56\x00"
    else:
        out += b"\x1d\x56\x01"
    return bytes(out)


def esc_beep(count: int = 1, duration: int = 1) -> bytes:
    c = clamp(int(count or 1), 1, 9)
    d = clamp(int(duration or 1), 1, 9)
    return bytes([0x1B, 0x42, c, d])


def esc_drawer(pin: int = 0, t1: int = 100, t2: int = 100) -> bytes:
    m = 0 if int(pin) == 0 else 1
    on = clamp(int(t1), 0, 255)
    off = clamp(int(t2), 0, 255)
    return bytes([0x1B, 0x70, m, on, off])


def esc_codepage(n: int) -> bytes:
    return bytes([0x1B, 0x74, clamp(n, 0, 255)])


CODEPAGE_MAP = {
    "cp437": (0, "cp437"),
    "cp860": (3, "cp860"),
    "cp863": (4, "cp863"),
    "cp865": (5, "cp865"),
    "cp1252": (16, "cp1252"),
    "cp866": (17, "cp866"),
    "cp852": (18, "cp852"),
    "cp858": (19, "cp858"),
}


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(content=exc.detail, status_code=exc.status_code)
    return json_error(str(exc.detail), exc.status_code)


@app.exception_handler(500)
async def handle_500(request: Request, exc: Exception):
    return json_error("Server error", 500)


# Middleware to enforce max content length
@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_CONTENT_LENGTH:
        return json_error("Payload too large", 413)
    return await call_next(request)


@app.get("/health")
async def health():
    return JSONResponse(content={"ok": True}, status_code=200)


@app.post("/print-image")
async def print_image(
    request: Request,
    image: UploadFile = File(...),
    printer_name: str = Depends(require_printer),
    max_width: str = Query(MAX_WIDTH_DEFAULT),
    mode: str = Query("gsv0"),
    align: str = Query("center"),
    lines_after: int = Query(0),
    beep_count: int = Query(1),
    beep_duration: int = Query(2),
    cut_mode: str = Query("partial"),
    cut_feed: int = Query(0),
):
    if not image.filename or not is_allowed_file(image.filename):
        return json_error("Invalid or no selected file", 400)

    filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    with open(filepath, "wb") as f:
        content = await image.read()
        f.write(content)

    invert = get_bool_arg(request, "invert", False)
    beep_after = get_bool_arg(request, "beep", True)
    cut_after = get_bool_arg(request, "cut", True)
    no_dither = get_bool_arg(request, "no_dither", False)

    try:
        # Check if printer has PPD support for hardware-level control
        has_ppd = printer_has_ppd(printer_name)
        
        if has_ppd:
            # Printer has PPD - send image file directly, let CUPS handle everything
            # PPD settings like FeedCutAfterJobEnd will control cutting timing
            lp = send_image_file(printer_name, filepath)
            
            return JSONResponse(
                content={
                    "message": "Print image sent (PPD mode)",
                    "printer": printer_name,
                    "mode": "ppd",
                    "note": "Cutting controlled by printer PPD settings (FeedCutAfterJobEnd)",
                    "lp_stdout": lp.stdout.decode("utf-8", "ignore"),
                },
                status_code=200,
            )
        
        # No PPD - use raw ESC/POS mode
        if not os.path.exists(PRINT_SCRIPT):
            return json_error(f"Missing {PRINT_SCRIPT}", 500)

        conv_cmd = [
            "python3",
            PRINT_SCRIPT,
            filepath,
            "--max-width",
            str(max_width),
            "--mode",
            mode,
            "--align",
            align,
        ]
        if invert:
            conv_cmd.append("--invert")
        if no_dither:
            conv_cmd.append("--no-dither")

        conv = subprocess.run(
            conv_cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Build complete payload with proper ESC/POS sequencing
        # The printer will execute commands in order and won't cut until done
        payload = bytearray()
        payload += esc_init()
        payload += conv.stdout
        
        # Add feed lines to ensure image is fully out of print head area
        # This is CRITICAL - the print head needs clearance before cutting
        min_feed_lines = 5  # Minimum lines to ensure image is past cutter
        total_feed = max(lines_after, min_feed_lines)
        if total_feed:
            payload += esc_feed(total_feed)
        
        # Now add beep and cut - these will execute AFTER all above completes
        if beep_after:
            payload += esc_beep(beep_count, beep_duration)
        if cut_after:
            payload += esc_cut(cut_mode, cut_feed)

        # Send as single atomic operation - printer processes sequentially
        lp = send_raw(printer_name, bytes(payload))

        return JSONResponse(
            content={
                "message": "Print image sent (raw mode)",
                "printer": printer_name,
                "mode": "raw",
                "lines_after": lines_after,
                "beep": bool(beep_after),
                "cut": bool(cut_after),
                "lp_stdout": lp.stdout.decode("utf-8", "ignore"),
            },
            status_code=200,
        )

    except subprocess.CalledProcessError as e:
        return json_error(
            "Printing failed",
            500,
            converter_stderr=e.stderr.decode("utf-8", "ignore"),
        )
    except Exception as e:
        return json_error(f"Unexpected server error: {e}", 500)
    finally:
        try:
            os.remove(filepath)
        except Exception:
            pass


@app.post("/print-text")
async def print_text(
    request: Request,
    printer_name: str = Depends(require_printer),
    align: str = Query("left"),
    underline: str = Query("none"),
    width: int = Query(1),
    height: int = Query(1),
    lines_after: int = Query(2),
    cut_mode: str = Query("partial"),
    cut_feed: int = Query(3),
    codepage: Optional[str] = Query(None),
):
    text = await get_json_or_form(request, "text")
    if not text:
        return json_error("Missing 'text' in body (JSON or form).", 400)

    bold = get_bool_arg(request, "bold", False)
    cut_after = get_bool_arg(request, "cut", False)

    cp_bytes = b""
    encoder = "utf-8"
    if codepage:
        idx, py_codec = CODEPAGE_MAP.get(
            codepage.lower(), (0, "cp437")
        )
        cp_bytes = esc_codepage(idx)
        encoder = py_codec

    try:
        payload = bytearray()
        payload += esc_init()
        payload += cp_bytes
        payload += esc_align(align)
        payload += esc_bold(bold)
        payload += esc_underline(underline)
        payload += esc_size(width, height)

        payload += (text + "\n").encode(encoder, errors="replace")
        payload += esc_feed(lines_after)

        if cut_after:
            payload += esc_cut(cut_mode, cut_feed)

        lp = send_raw(printer_name, bytes(payload))

        return JSONResponse(
            content={
                "message": "Text sent",
                "printer": printer_name,
                "lp_stdout": lp.stdout.decode("utf-8", "ignore"),
            },
            status_code=200,
        )
    except subprocess.CalledProcessError as e:
        return json_error(
            "Failed to send text",
            500,
            stderr=e.stderr.decode("utf-8", "ignore"),
        )
    except Exception as e:
        return json_error(f"Unexpected server error: {e}", 500)


@app.get("/beep")
async def beep(
    request: Request,
    printer_name: str = Depends(require_printer),
    count: int = Query(1),
    duration: Optional[int] = Query(None),
    time: Optional[int] = Query(None),
):
    try:
        # Handle the 'time' parameter fallback
        if time is not None and duration is None:
            duration = time
        if duration is None:
            duration = 1

        payload = esc_beep(count, duration)
        send_raw(printer_name, payload)
        return JSONResponse(
            content={
                "message": "Beep sent",
                "printer": printer_name,
                "count": clamp(count, 1, 9),
                "duration_units_100ms": clamp(duration, 1, 9),
            },
            status_code=200,
        )
    except subprocess.CalledProcessError as e:
        return json_error(
            "Failed to send beep",
            500,
            stderr=e.stderr.decode("utf-8", "ignore"),
        )
    except Exception as e:
        return json_error(f"Unexpected server error: {e}", 500)


@app.api_route("/cut", methods=["GET", "POST"])
async def cut(
    printer_name: str = Depends(require_printer),
    mode: str = Query("partial"),
    feed: int = Query(3),
):
    try:
        payload = esc_cut(mode, feed)
        send_raw(printer_name, payload)
        return JSONResponse(
            content={"message": "Cut sent", "printer": printer_name},
            status_code=200,
        )
    except subprocess.CalledProcessError as e:
        return json_error(
            "Failed to send cut",
            500,
            stderr=e.stderr.decode("utf-8", "ignore"),
        )
    except Exception as e:
        return json_error(f"Unexpected server error: {e}", 500)


@app.api_route("/drawer", methods=["GET", "POST"])
async def drawer(
    printer_name: str = Depends(require_printer),
    pin: int = Query(0),
    t1: int = Query(100),
    t2: int = Query(100),
):
    try:
        payload = esc_drawer(pin, t1, t2)
        send_raw(printer_name, payload)
        return JSONResponse(
            content={
                "message": "Cash drawer pulse sent",
                "printer": printer_name,
                "pin": 0 if pin == 0 else 1,
                "t1": clamp(t1, 0, 255),
                "t2": clamp(t2, 0, 255),
            },
            status_code=200,
        )
    except subprocess.CalledProcessError as e:
        return json_error(
            "Failed to open cash drawer",
            500,
            stderr=e.stderr.decode("utf-8", "ignore"),
        )
    except Exception as e:
        return json_error(f"Unexpected server error: {e}", 500)


@app.api_route("/feed", methods=["GET", "POST"])
async def feed(
    printer_name: str = Depends(require_printer),
    lines: int = Query(3),
):
    try:
        payload = esc_feed(lines)
        send_raw(printer_name, payload)
        return JSONResponse(
            content={
                "message": "Feed sent",
                "printer": printer_name,
                "lines": clamp(lines, 0, 255),
            },
            status_code=200,
        )
    except subprocess.CalledProcessError as e:
        return json_error(
            "Failed to feed",
            500,
            stderr=e.stderr.decode("utf-8", "ignore"),
        )
    except Exception as e:
        return json_error(f"Unexpected server error: {e}", 500)


@app.post("/print-raw")
async def print_raw(
    request: Request,
    printer_name: str = Depends(require_printer),
):
    b64 = await get_json_or_form(request, "base64")
    hx = await get_json_or_form(request, "hex")

    if not b64 and not hx:
        return json_error("Provide 'base64' or 'hex' in body.", 400)

    try:
        if b64:
            data = base64.b64decode(b64, validate=True)
        else:
            data = binascii.unhexlify(hx.strip())
    except (binascii.Error, ValueError) as e:
        return json_error(f"Invalid payload encoding: {e}", 400)

    try:
        lp = send_raw(printer_name, data)
        return JSONResponse(
            content={
                "message": "Raw data sent",
                "printer": printer_name,
                "bytes": len(data),
                "lp_stdout": lp.stdout.decode("utf-8", "ignore"),
            },
            status_code=200,
        )
    except subprocess.CalledProcessError as e:
        return json_error(
            "Failed to send raw data",
            500,
            stderr=e.stderr.decode("utf-8", "ignore"),
        )
    except Exception as e:
        return json_error(f"Unexpected server error: {e}", 500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)