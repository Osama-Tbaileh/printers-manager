import os
import uuid
import base64
import binascii
import subprocess
from typing import Optional

from fastapi import (
    FastAPI,
    Request,
    Query,
    File,
    UploadFile,
    HTTPException,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from PIL import Image

# Import python-escpos library with DUMMY printer (generates bytes, doesn't send)
from escpos.printer import Dummy
from escpos.exceptions import Error as EscposError

# Load environment variables
load_dotenv()

# Configuration
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
ALLOWED_EXTENSIONS = set(os.getenv("ALLOWED_EXTENSIONS", "png,jpg,jpeg,bmp,gif").split(","))
MAX_WIDTH_DEFAULT = int(os.getenv("MAX_WIDTH_DEFAULT", "576"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20")) * 1024 * 1024
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "3006"))

# Printer names - these MUST match CUPS printer names
# python-escpos generates commands, CUPS sends them (best of both worlds!)
PRINTERS = ["printer_1", "printer_2"]

app = FastAPI()

# CORS configuration
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


def validate_printer(printer_name: str) -> str:
    """Validate printer name and return it"""
    if not printer_name:
        raise HTTPException(status_code=400, detail={"error": "Missing printer parameter"})
    
    if printer_name not in PRINTERS:
        raise HTTPException(status_code=400, detail={"error": f"Unknown printer: {printer_name}. Available: {PRINTERS}"})
    
    return printer_name


def verify_cups_printer(printer_name: str):
    """Verify printer exists in CUPS (optional check)"""
    try:
        subprocess.run(
            ["lpstat", "-p", printer_name],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        # Printer not in CUPS - that's okay, we'll add it
        pass


def send_to_cups(printer_name: str, data: bytes):
    """Send raw ESC/POS data to CUPS printer queue"""
    try:
        result = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw"],
            input=data,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail={"error": f"CUPS printing failed: {e.stderr.decode('utf-8', 'ignore')}"}
        )


def clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


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


@app.get("/")
@app.get("/health")
async def health():
    return JSONResponse(content={
        "ok": True,
        "status": "running",
        "printers": PRINTERS,
        "backend": "python-escpos (Dummy) + CUPS",
        "method": "escpos generates commands, CUPS sends them"
    }, status_code=200)


@app.get("/list-printers")
async def list_printers():
    """List all configured printers from CUPS"""
    try:
        result = subprocess.run(
            ["lpstat", "-p"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        # Parse lpstat output
        printer_list = []
        for line in result.stdout.strip().split('\n'):
            if line.startswith('printer '):
                parts = line.split()
                if len(parts) >= 2:
                    printer_list.append({
                        "name": parts[1],
                        "status": " ".join(parts[3:]) if len(parts) > 3 else "unknown"
                    })
        
        return JSONResponse(content={
            "printers": printer_list,
            "count": len(printer_list),
            "configured": PRINTERS
        }, status_code=200)
    except:
        return JSONResponse(content={
            "printers": [],
            "count": 0,
            "configured": PRINTERS,
            "note": "Run lpstat -p to see CUPS printers"
        }, status_code=200)


@app.post("/print-image")
async def print_image(
    request: Request,
    image: UploadFile = File(...),
    printer: Optional[str] = Query(None),
    p: Optional[str] = Query(None),
    printer_name: Optional[str] = Query(None),
    max_width: int = Query(MAX_WIDTH_DEFAULT),
    lines_after: int = Query(5),
    cut: bool = Query(True),
    center: bool = Query(True),
    high_density: bool = Query(True),
):
    """
    Print image using python-escpos library with direct network connection.
    This properly handles image buffering and prevents cutting mid-image.
    """
    # Resolve printer name from various parameters (backward compatible)
    pname = p or printer or printer_name
    if not pname:
        pname = "printer_1"  # Default
    
    if not image.filename or not is_allowed_file(image.filename):
        return json_error("Invalid or no selected file", 400)

    filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    # Read image data
    content = await image.read()
    
    # Save temporarily for processing
    with open(filepath, "wb") as f:
        f.write(content)

    try:
        # Validate printer
        validate_printer(pname)
        
        # Use Dummy printer to generate ESC/POS commands (doesn't send anything)
        escpos = Dummy()
        
        # Open and process image
        img = Image.open(filepath)
        
        # Convert to RGB if necessary
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # Resize image to fit printer width while maintaining aspect ratio
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Set alignment
        if center:
            escpos.set(align='center')
        
        # Generate image ESC/POS commands
        # python-escpos handles proper buffering and image conversion
        escpos.image(
            img,
            impl='bitImageRaster',  # Most reliable method
            high_density_vertical=high_density,
            high_density_horizontal=high_density,
        )
        
        # Reset alignment
        if center:
            escpos.set(align='left')
        
        # Important: Feed paper to ensure image is fully out before cutting
        if lines_after > 0:
            escpos.text('\n' * lines_after)
        else:
            escpos.text('\n\n')  # At least 2 lines for safety
        
        # Cut paper
        if cut:
            escpos.cut()
        
        # Get the generated ESC/POS bytes
        escpos_bytes = escpos.output
        
        # Send through CUPS (queue management!)
        send_to_cups(pname, escpos_bytes)

        return JSONResponse(
            content={
                "message": "Image printed successfully",
                "printer": pname,
                "image_width": img.width,
                "image_height": img.height,
                "lines_after": lines_after,
                "cut": cut,
            },
            status_code=200,
        )

    except EscposError as e:
        return json_error(f"Printer error: {str(e)}", 500)
    except Exception as e:
        return json_error(f"Server error: {e}", 500)
    finally:
        try:
            os.remove(filepath)
        except Exception:
            pass


@app.post("/print-text")
async def print_text(
    request: Request,
    printer: Optional[str] = Query(None),
    p: Optional[str] = Query(None),
    printer_name: Optional[str] = Query(None),
    align: str = Query("left"),
    bold: bool = Query(False),
    underline: int = Query(0),
    width: int = Query(1),
    height: int = Query(1),
    lines_after: int = Query(2),
    cut: bool = Query(False),
):
    """Print text to thermal printer"""
    # Resolve printer name
    pname = p or printer or printer_name
    if not pname:
        pname = "printer_1"
    
    # Get text from form data or JSON
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            text = data.get("text")
        except:
            text = None
    else:
        form = await request.form()
        text = form.get("text")
    
    if not text:
        return json_error("Missing 'text' in body", 400)

    try:
        validate_printer(pname)
        
        # Use Dummy printer to generate ESC/POS commands
        escpos = Dummy()
        
        # Set text formatting
        escpos.set(
            align=align,
            bold=bold,
            underline=underline,
            width=clamp(width, 1, 8),
            height=clamp(height, 1, 8),
        )
        
        # Print text
        escpos.text(text)
        if not text.endswith('\n'):
            escpos.text('\n')
        
        # Reset formatting
        escpos.set()
        
        # Feed lines
        if lines_after > 0:
            escpos.text('\n' * lines_after)
        
        # Cut if requested
        if cut:
            escpos.cut()
        
        # Send through CUPS
        send_to_cups(pname, escpos.output)

        return JSONResponse(
            content={
                "message": "Text printed successfully",
                "printer": pname,
            },
            status_code=200,
        )
    except EscposError as e:
        return json_error(f"Printer error: {str(e)}", 500)
    except Exception as e:
        return json_error(f"Server error: {e}", 500)


@app.get("/beep")
@app.post("/beep")
async def beep(
    printer: Optional[str] = Query(None),
    p: Optional[str] = Query(None),
    printer_name: Optional[str] = Query(None),
    count: int = Query(1),
    duration: int = Query(1),
):
    """Make printer beep"""
    pname = p or printer or printer_name
    if not pname:
        pname = "printer_1"
    
    try:
        validate_printer(pname)
        
        # ESC B n t - Buzzer command
        count_val = clamp(count, 1, 9)
        duration_val = clamp(duration, 1, 9)
        
        # Generate beep command
        beep_bytes = b'\x1b\x42' + bytes([count_val, duration_val])
        
        # Send through CUPS
        send_to_cups(pname, beep_bytes)
        
        return JSONResponse(
            content={
                "message": "Beep sent",
                "printer": pname,
                "count": count_val,
                "duration_units_100ms": duration_val,
            },
            status_code=200,
        )
    except EscposError as e:
        return json_error(f"Printer error: {str(e)}", 500)
    except Exception as e:
        return json_error(f"Server error: {e}", 500)


@app.api_route("/cut", methods=["GET", "POST"])
async def cut(
    printer: Optional[str] = Query(None),
    p: Optional[str] = Query(None),
    printer_name: Optional[str] = Query(None),
    feed: int = Query(3),
    mode: str = Query("partial"),
):
    """Cut paper"""
    pname = p or printer or printer_name
    if not pname:
        pname = "printer_1"
    
    try:
        validate_printer(pname)
        
        # Use Dummy printer to generate commands
        escpos = Dummy()
        
        # Feed before cutting
        if feed > 0:
            escpos.text('\n' * feed)
        
        # Cut
        escpos.cut()
        
        # Send through CUPS
        send_to_cups(pname, escpos.output)
        
        return JSONResponse(
            content={"message": "Paper cut", "printer": pname},
            status_code=200,
        )
    except EscposError as e:
        return json_error(f"Printer error: {str(e)}", 500)
    except Exception as e:
        return json_error(f"Server error: {e}", 500)


@app.api_route("/drawer", methods=["GET", "POST"])
async def drawer(
    printer: Optional[str] = Query(None),
    p: Optional[str] = Query(None),
    printer_name: Optional[str] = Query(None),
    pin: int = Query(0),
    t1: int = Query(100),
    t2: int = Query(100),
):
    """Open cash drawer"""
    pname = p or printer or printer_name
    if not pname:
        pname = "printer_1"
    
    try:
        validate_printer(pname)
        
        # ESC p m t1 t2 - Cash drawer command
        pin_val = 0 if pin == 0 else 1
        t1_val = clamp(t1, 0, 255)
        t2_val = clamp(t2, 0, 255)
        
        drawer_bytes = b'\x1b\x70' + bytes([pin_val, t1_val, t2_val])
        
        # Send through CUPS
        send_to_cups(pname, drawer_bytes)
        
        return JSONResponse(
            content={
                "message": "Cash drawer opened",
                "printer": pname,
                "pin": pin_val,
            },
            status_code=200,
        )
    except EscposError as e:
        return json_error(f"Printer error: {str(e)}", 500)
    except Exception as e:
        return json_error(f"Server error: {e}", 500)


@app.api_route("/feed", methods=["GET", "POST"])
async def feed(
    printer: Optional[str] = Query(None),
    p: Optional[str] = Query(None),
    printer_name: Optional[str] = Query(None),
    lines: int = Query(3),
):
    """Feed paper lines"""
    pname = p or printer or printer_name
    if not pname:
        pname = "printer_1"
    
    try:
        validate_printer(pname)
        
        # Use Dummy printer to generate commands
        escpos = Dummy()
        lines_val = clamp(lines, 0, 255)
        escpos.text('\n' * lines_val)
        
        # Send through CUPS
        send_to_cups(pname, escpos.output)
        
        return JSONResponse(
            content={
                "message": "Paper fed",
                "printer": pname,
                "lines": lines_val,
            },
            status_code=200,
        )
    except EscposError as e:
        return json_error(f"Printer error: {str(e)}", 500)
    except Exception as e:
        return json_error(f"Server error: {e}", 500)


@app.post("/print-raw")
async def print_raw(
    request: Request,
    printer: Optional[str] = Query(None),
    p: Optional[str] = Query(None),
    printer_name: Optional[str] = Query(None),
):
    """Send raw ESC/POS data"""
    pname = p or printer or printer_name
    if not pname:
        pname = "printer_1"
    
    # Get data from form or JSON
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            b64 = data.get("base64")
            hx = data.get("hex")
        except:
            b64 = None
            hx = None
    else:
        form = await request.form()
        b64 = form.get("base64")
        hx = form.get("hex")
    
    if not b64 and not hx:
        return json_error("Provide 'base64' or 'hex' in body", 400)
    
    try:
        if b64:
            raw_data = base64.b64decode(b64)
        else:
            raw_data = binascii.unhexlify(hx.strip())
    except Exception as e:
        return json_error(f"Invalid encoding: {e}", 400)
    
    try:
        validate_printer(pname)
        
        # Send raw data directly through CUPS
        send_to_cups(pname, raw_data)
        
        return JSONResponse(
            content={
                "message": "Raw data sent",
                "printer": pname,
                "bytes": len(raw_data),
            },
            status_code=200,
        )
    except EscposError as e:
        return json_error(f"Printer error: {str(e)}", 500)
    except Exception as e:
        return json_error(f"Server error: {e}", 500)


if __name__ == "__main__":
    import uvicorn
    print(f"🖨️  Thermal Printer Server - HYBRID MODE")
    print(f"📦 python-escpos generates ESC/POS commands")
    print(f"📋 CUPS handles queue management & sending")
    print(f"🚀 Server listening on {SERVER_HOST}:{SERVER_PORT}")
    print(f"")
    print(f"Configured printers: {', '.join(PRINTERS)}")
    print(f"")
    print(f"Make sure printers are in CUPS:")
    print(f"  sudo lpadmin -p printer_1 -v socket://192.168.1.87:9100 -E")
    print(f"  sudo lpadmin -p printer_2 -v socket://192.168.1.105:9100 -E")
    print(f"")
    print(f"Test with: curl 'http://localhost:{SERVER_PORT}/beep?p=printer_1'")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
