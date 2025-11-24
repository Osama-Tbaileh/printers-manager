import os
import uuid
import base64
import binascii
import subprocess
import tempfile
from typing import Optional
from io import BytesIO

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
from PIL import Image

# Import python-escpos library
try:
    from escpos import printer
    from escpos.printer import CupsPrinter
    from escpos.exceptions import Error as EscposError
except ImportError:
    raise ImportError(
        "python-escpos is required. Install with: pip install python-escpos"
    )

# Load environment variables from .env file
load_dotenv()

# Configuration - can be customized via .env file
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "png,jpg,jpeg,bmp").split(","))
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


def get_cups_printer(printer_name: str) -> CupsPrinter:
    """
    Get a CUPS printer instance using python-escpos.
    This maintains CUPS integration for queue management.
    """
    try:
        return CupsPrinter(printer_name=printer_name)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to connect to printer: {str(e)}"}
        )


def send_raw(printer: str, data: bytes):
    """Fallback raw printing using CUPS lp command"""
    return subprocess.run(
        ["lp", "-d", printer, "-o", "raw"],
        input=data,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


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
    """
    Print image using python-escpos library.
    This properly handles image buffering and prevents cutting mid-image.
    """
    if not image.filename or not is_allowed_file(image.filename):
        return json_error("Invalid or no selected file", 400)

    filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    # Read image data
    content = await image.read()
    
    # Save temporarily for processing
    with open(filepath, "wb") as f:
        f.write(content)

    invert = get_bool_arg(request, "invert", False)
    beep_after = get_bool_arg(request, "beep", True)
    cut_after = get_bool_arg(request, "cut", True)
    no_dither = get_bool_arg(request, "no_dither", False)

    try:
        # Get CUPS printer instance
        p = get_cups_printer(printer_name)
        
        # Open and process image
        img = Image.open(filepath)
        
        # Convert to RGB if necessary
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # Convert max_width to int for processing
        max_width_int = int(max_width)
        
        # Resize image to fit printer width while maintaining aspect ratio
        if img.width > max_width_int:
            ratio = max_width_int / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width_int, new_height), Image.Resampling.LANCZOS)
        
        # Invert colors if requested
        if invert:
            if img.mode == 'L':
                img = Image.eval(img, lambda x: 255 - x)
            elif img.mode == 'RGB':
                from PIL import ImageOps
                img = ImageOps.invert(img)
        
        # Set alignment
        align_map = {"left": "left", "center": "center", "right": "right"}
        p.set(align=align_map.get(align, "center"))
        
        # Print the image using escpos library
        # The library handles proper buffering and ensures the image is fully sent
        # before any subsequent commands (like cut) are executed
        impl = "bitImageColumn" if mode == "gsv0" else "graphics"
        
        # Add extra feed lines to ensure image is fully printed before cutting
        # This is critical to prevent mid-image cutting
        p.image(
            img,
            impl=impl,
            fragment_height=960,  # Process in larger fragments for better reliability
            high_density_vertical=True,
            high_density_horizontal=True,
        )
        
        # Important: Add paper feed to ensure image is fully out of the print head
        # before cutting. This prevents the cutting-in-middle issue.
        if lines_after > 0:
            p.ln(lines_after)
        else:
            # Always add at least some feed lines after image for safety
            p.ln(2)
        
        # Beep if requested
        if beep_after:
            # Using raw ESC/POS command for beep as escpos library doesn't have direct method
            p._raw(esc_beep(beep_count, beep_duration))
        
        # Cut paper if requested
        # By this point, the image should be fully printed and fed past the cutter
        if cut_after:
            if cut_feed > 0:
                p.ln(cut_feed)
            
            # Use the library's cut method which properly handles the command
            if cut_mode == "full":
                p.cut(mode='FULL')
            else:
                p.cut(mode='PART')
        
        # Close printer connection to flush all commands
        p.close()

        return JSONResponse(
            content={
                "message": "Print image sent successfully using escpos",
                "printer": printer_name,
                "image_width": img.width,
                "image_height": img.height,
                "lines_after": lines_after,
                "beep": bool(beep_after),
                "cut": bool(cut_after),
                "method": "python-escpos with CUPS backend",
            },
            status_code=200,
        )

    except EscposError as e:
        return json_error(
            f"Escpos printing failed: {str(e)}",
            500,
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
    """
    Print text using python-escpos library for better control.
    """
    text = await get_json_or_form(request, "text")
    if not text:
        return json_error("Missing 'text' in body (JSON or form).", 400)

    bold = get_bool_arg(request, "bold", False)
    cut_after = get_bool_arg(request, "cut", False)

    try:
        # Get CUPS printer instance
        p = get_cups_printer(printer_name)
        
        # Set codepage if specified
        if codepage:
            cp_lower = codepage.lower()
            if cp_lower in CODEPAGE_MAP:
                idx, py_codec = CODEPAGE_MAP[cp_lower]
                p.charcode(code=py_codec.upper())
        
        # Set text formatting
        align_map = {"left": "left", "center": "center", "right": "right"}
        p.set(
            align=align_map.get(align, "left"),
            bold=bold,
            underline=1 if underline == "single" else 2 if underline == "double" else 0,
            width=clamp(width, 1, 8),
            height=clamp(height, 1, 8),
        )
        
        # Print text
        p.text(text + "\n")
        
        # Feed lines
        if lines_after > 0:
            p.ln(lines_after)
        
        # Cut if requested
        if cut_after:
            if cut_feed > 0:
                p.ln(cut_feed)
            
            if cut_mode == "full":
                p.cut(mode='FULL')
            else:
                p.cut(mode='PART')
        
        # Close printer connection
        p.close()

        return JSONResponse(
            content={
                "message": "Text sent successfully using escpos",
                "printer": printer_name,
                "method": "python-escpos with CUPS backend",
            },
            status_code=200,
        )
    except EscposError as e:
        return json_error(
            f"Escpos text printing failed: {str(e)}",
            500,
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
    """Send beep command to printer"""
    try:
        # Handle the 'time' parameter fallback
        if time is not None and duration is None:
            duration = time
        if duration is None:
            duration = 1

        # Use CUPS printer for consistency
        p = get_cups_printer(printer_name)
        p._raw(esc_beep(count, duration))
        p.close()
        
        return JSONResponse(
            content={
                "message": "Beep sent",
                "printer": printer_name,
                "count": clamp(count, 1, 9),
                "duration_units_100ms": clamp(duration, 1, 9),
            },
            status_code=200,
        )
    except Exception as e:
        return json_error(f"Failed to send beep: {e}", 500)


@app.api_route("/cut", methods=["GET", "POST"])
async def cut(
    printer_name: str = Depends(require_printer),
    mode: str = Query("partial"),
    feed: int = Query(3),
):
    """Send cut command to printer"""
    try:
        p = get_cups_printer(printer_name)
        
        # Feed paper before cutting
        if feed > 0:
            p.ln(feed)
        
        # Cut paper
        if mode == "full":
            p.cut(mode='FULL')
        else:
            p.cut(mode='PART')
        
        p.close()
        
        return JSONResponse(
            content={"message": "Cut sent", "printer": printer_name},
            status_code=200,
        )
    except Exception as e:
        return json_error(f"Failed to send cut: {e}", 500)


@app.api_route("/drawer", methods=["GET", "POST"])
async def drawer(
    printer_name: str = Depends(require_printer),
    pin: int = Query(0),
    t1: int = Query(100),
    t2: int = Query(100),
):
    """Open cash drawer"""
    try:
        p = get_cups_printer(printer_name)
        
        # The escpos library has a cashdraw method
        # pin: 0 or 1 (drawer pin 2 or 5)
        # Using raw command for more control over timing
        p._raw(esc_drawer(pin, t1, t2))
        p.close()
        
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
    except Exception as e:
        return json_error(f"Failed to open cash drawer: {e}", 500)


@app.api_route("/feed", methods=["GET", "POST"])
async def feed(
    printer_name: str = Depends(require_printer),
    lines: int = Query(3),
):
    """Feed paper lines"""
    try:
        p = get_cups_printer(printer_name)
        p.ln(clamp(lines, 0, 255))
        p.close()
        
        return JSONResponse(
            content={
                "message": "Feed sent",
                "printer": printer_name,
                "lines": clamp(lines, 0, 255),
            },
            status_code=200,
        )
    except Exception as e:
        return json_error(f"Failed to feed: {e}", 500)


@app.post("/print-raw")
async def print_raw(
    request: Request,
    printer_name: str = Depends(require_printer),
):
    """
    Send raw ESC/POS data to printer.
    Accepts base64 or hex encoded data.
    """
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
        p = get_cups_printer(printer_name)
        p._raw(data)
        p.close()
        
        return JSONResponse(
            content={
                "message": "Raw data sent",
                "printer": printer_name,
                "bytes": len(data),
            },
            status_code=200,
        )
    except Exception as e:
        return json_error(f"Failed to send raw data: {e}", 500)


@app.get("/list-printers")
async def list_printers():
    """
    List all available CUPS printers.
    This endpoint uses CUPS to discover printers.
    """
    try:
        result = subprocess.run(
            ["lpstat", "-p"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        # Parse lpstat output
        printers = []
        for line in result.stdout.strip().split('\n'):
            if line.startswith('printer '):
                # Format: "printer PrinterName is idle..."
                parts = line.split()
                if len(parts) >= 2:
                    printers.append({
                        "name": parts[1],
                        "status": " ".join(parts[3:]) if len(parts) > 3 else "unknown"
                    })
        
        return JSONResponse(
            content={
                "message": "Printers listed successfully",
                "printers": printers,
                "count": len(printers),
            },
            status_code=200,
        )
    except subprocess.CalledProcessError as e:
        return json_error(
            f"Failed to list printers: {e.stderr}",
            500,
        )
    except Exception as e:
        return json_error(f"Unexpected error: {e}", 500)


@app.get("/printer-status")
async def printer_status(
    printer_name: str = Depends(require_printer),
):
    """
    Get detailed status of a specific printer using CUPS.
    """
    try:
        # Get printer status
        result = subprocess.run(
            ["lpstat", "-p", printer_name, "-l"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        # Get printer jobs
        jobs_result = subprocess.run(
            ["lpstat", "-o", printer_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        return JSONResponse(
            content={
                "message": "Printer status retrieved",
                "printer": printer_name,
                "status": result.stdout.strip(),
                "jobs": jobs_result.stdout.strip() if jobs_result.returncode == 0 else "No jobs",
            },
            status_code=200,
        )
    except subprocess.CalledProcessError as e:
        return json_error(
            f"Failed to get printer status: {e.stderr}",
            500,
        )
    except Exception as e:
        return json_error(f"Unexpected error: {e}", 500)


if __name__ == "__main__":
    import uvicorn
    print(f"Starting printer server with python-escpos integration...")
    print(f"CUPS backend will be used for printer queue management")
    print(f"Server will listen on {SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)

