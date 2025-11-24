import os
import uuid
import base64
import binascii
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

# Import python-escpos library with NETWORK backend (direct IP connection)
from escpos.printer import Network
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

# Printer configurations - DIRECT IP addresses (no CUPS bullshit)
PRINTERS = {
    "printer_1": {"host": os.getenv("PRINTER_1_IP", "192.168.1.87"), "port": 9100},
    "printer_2": {"host": os.getenv("PRINTER_2_IP", "192.168.1.105"), "port": 9100},
}

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


def get_printer_config(printer_name: str):
    """Get printer name, supporting aliases like 'p' and 'printer'"""
    if not printer_name:
        raise HTTPException(status_code=400, detail={"error": "Missing printer parameter"})
    
    if printer_name not in PRINTERS:
        raise HTTPException(status_code=400, detail={"error": f"Unknown printer: {printer_name}. Available: {list(PRINTERS.keys())}"})
    
    return PRINTERS[printer_name]


def get_printer(printer_name: str) -> Network:
    """Get a fresh Network printer connection"""
    config = get_printer_config(printer_name)
    try:
        return Network(config["host"], port=config["port"])
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": f"Cannot connect to {printer_name} at {config['host']}:{config['port']}: {str(e)}"})


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
        "printers": list(PRINTERS.keys()),
        "backend": "python-escpos with Network (direct IP)"
    }, status_code=200)


@app.get("/list-printers")
async def list_printers():
    """List all configured printers"""
    printer_list = []
    for name, config in PRINTERS.items():
        printer_list.append({
            "name": name,
            "host": config["host"],
            "port": config["port"]
        })
    return JSONResponse(content={
        "printers": printer_list,
        "count": len(printer_list)
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
        # Get printer connection
        printer_obj = get_printer(pname)
        
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
            printer_obj.set(align='center')
        
        # Print the image using escpos library
        # This handles proper buffering and ensures the image is fully sent
        printer_obj.image(
            img,
            impl='bitImageRaster',  # Most reliable method
            high_density_vertical=high_density,
            high_density_horizontal=high_density,
        )
        
        # Reset alignment
        if center:
            printer_obj.set(align='left')
        
        # Important: Feed paper to ensure image is fully out before cutting
        if lines_after > 0:
            printer_obj.text('\n' * lines_after)
        else:
            printer_obj.text('\n\n')  # At least 2 lines for safety
        
        # Cut paper
        if cut:
            printer_obj.cut()
        
        # Close connection (flushes all data)
        printer_obj.close()

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
        printer_obj = get_printer(pname)
        
        # Set text formatting
        printer_obj.set(
            align=align,
            bold=bold,
            underline=underline,
            width=clamp(width, 1, 8),
            height=clamp(height, 1, 8),
        )
        
        # Print text
        printer_obj.text(text)
        if not text.endswith('\n'):
            printer_obj.text('\n')
        
        # Reset formatting
        printer_obj.set()
        
        # Feed lines
        if lines_after > 0:
            printer_obj.text('\n' * lines_after)
        
        # Cut if requested
        if cut:
            printer_obj.cut()
        
        printer_obj.close()

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
        printer_obj = get_printer(pname)
        
        # ESC B n t - Buzzer command
        count_val = clamp(count, 1, 9)
        duration_val = clamp(duration, 1, 9)
        
        # Send beep command
        printer_obj._raw(b'\x1b\x42' + bytes([count_val, duration_val]))
        printer_obj.close()
        
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
        printer_obj = get_printer(pname)
        
        # Feed before cutting
        if feed > 0:
            printer_obj.text('\n' * feed)
        
        # Cut
        printer_obj.cut()
        printer_obj.close()
        
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
        printer_obj = get_printer(pname)
        
        # ESC p m t1 t2 - Cash drawer command
        pin_val = 0 if pin == 0 else 1
        t1_val = clamp(t1, 0, 255)
        t2_val = clamp(t2, 0, 255)
        
        printer_obj._raw(b'\x1b\x70' + bytes([pin_val, t1_val, t2_val]))
        printer_obj.close()
        
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
        printer_obj = get_printer(pname)
        
        lines_val = clamp(lines, 0, 255)
        printer_obj.text('\n' * lines_val)
        printer_obj.close()
        
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
        printer_obj = get_printer(pname)
        printer_obj._raw(raw_data)
        printer_obj.close()
        
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
    print(f"🖨️  Thermal Printer Server with python-escpos")
    print(f"📡 Using Network backend (direct IP connections)")
    print(f"🚀 Server listening on {SERVER_HOST}:{SERVER_PORT}")
    print(f"")
    print(f"Available printers:")
    for name, config in PRINTERS.items():
        print(f"  - {name}: {config['host']}:{config['port']}")
    print(f"")
    print(f"Test with: curl 'http://localhost:{SERVER_PORT}/beep?p=printer_1'")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
