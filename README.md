# Printer Manager API

A modern FastAPI-based REST API for managing ESC/POS thermal printers. This server provides endpoints for printing text, images, controlling paper feed, cutting, beeping, and opening cash drawers.

## Features

- 🖨️ **Print Text** - Send formatted text with customizable alignment, size, bold, and underline
- 🖼️ **Print Images** - Print images (PNG, JPG, JPEG, BMP) with automatic conversion
- ✂️ **Paper Control** - Cut paper and feed lines
- 🔔 **Beep Control** - Trigger printer beeper
- 💰 **Cash Drawer** - Open cash drawer connected to printer
- 🔧 **Raw Commands** - Send raw ESC/POS commands via base64 or hex
- 📚 **Auto Documentation** - Interactive API docs via Swagger UI
- 🌐 **CORS Enabled** - Ready for web applications
- ⚙️ **Environment Configuration** - Easy configuration via .env files
- 🔐 **API Key Authentication** - Secure all endpoints with API key

## Requirements

- Python 3.8+
- CUPS (Common UNIX Printing System)
- A configured thermal printer accessible via `lp` command
- `print_image_any.py` script (for image printing)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/printers-manager.git
cd printers-manager
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment (Required)

Create a `.env` file:

```bash
cp .env.example .env
nano .env
```

Set your API key:
```env
SERVER_HOST=0.0.0.0
SERVER_PORT=3006
API_KEY=your_secret_api_key_here
```

Generate a secure API key:
```bash
openssl rand -hex 32
```

## Running the Server

### Development Mode

```bash
# Make sure virtual environment is activated
python server.py
```

The server will start on `http://0.0.0.0:3006`

### Production Mode

```bash
uvicorn server:app --host 0.0.0.0 --port 3006 --workers 4
```

### With Auto-Reload (Development)

```bash
uvicorn server:app --host 0.0.0.0 --port 3006 --reload
```

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:3006/docs
- **ReDoc**: http://localhost:3006/redoc
- **OpenAPI JSON**: http://localhost:3006/openapi.json

## API Endpoints

### Health Check

```http
GET /health
```

Returns server health status.

**Headers:**
```
X-API-Key: your_api_key_here
```

**Response:**
```json
{
  "ok": true
}
```

**Note:** All endpoints require the `X-API-Key` header with your configured API key.

---

### Print Image

```http
POST /print-image?printer=<printer_name>
```

Print an image file to a thermal printer.

**Query Parameters:**
- `printer` (required) - Printer name (alias: `p`)
- `verify` (optional) - Verify printer exists (`1`, `true`, `yes`)
- `max_width` (optional) - Maximum width in pixels (default: `576`)
- `mode` (optional) - Print mode (default: `gsv0`)
- `align` (optional) - Alignment: `left`, `center`, `right` (default: `center`)
- `invert` (optional) - Invert image colors (default: `false`)
- `lines_after` (optional) - Feed lines after printing (default: `0`)
- `beep` (optional) - Beep after printing (default: `true`)
- `beep_count` (optional) - Number of beeps (default: `1`)
- `beep_duration` (optional) - Beep duration units (default: `2`)
- `cut` (optional) - Cut paper after printing (default: `true`)
- `cut_mode` (optional) - Cut mode: `partial` or `full` (default: `partial`)
- `cut_feed` (optional) - Feed lines before cut (default: `0`)

**Body:**
- `image` - Image file (multipart/form-data)

**Example:**
```bash
curl -X POST "http://localhost:3006/print-image?printer=TP80" \
  -H "X-API-Key: your_api_key_here" \
  -F "image=@receipt.png"
```

---

### Print Text

```http
POST /print-text?printer=<printer_name>
```

Print formatted text to a thermal printer.

**Query Parameters:**
- `printer` (required) - Printer name
- `align` (optional) - Alignment: `left`, `center`, `right` (default: `left`)
- `bold` (optional) - Bold text (default: `false`)
- `underline` (optional) - Underline: `none`, `single`, `double` (default: `none`)
- `width` (optional) - Text width multiplier 1-8 (default: `1`)
- `height` (optional) - Text height multiplier 1-8 (default: `1`)
- `lines_after` (optional) - Feed lines after (default: `2`)
- `cut` (optional) - Cut after printing (default: `false`)
- `cut_mode` (optional) - Cut mode (default: `partial`)
- `cut_feed` (optional) - Feed before cut (default: `3`)
- `codepage` (optional) - Code page: `cp437`, `cp860`, `cp863`, `cp865`, `cp1252`, `cp866`, `cp852`, `cp858`

**Body (Form):**
- `text` - Text to print

**Example:**
```bash
curl -X POST "http://localhost:3006/print-text?printer=TP80&bold=true&align=center" \
  -H "X-API-Key: your_api_key_here" \
  -F "text=Hello World!"
```

**Example (JSON):**
```bash
curl -X POST "http://localhost:3006/print-text?printer=TP80&bold=true" \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello World!"}'
```

---

### Beep

```http
GET /beep?printer=<printer_name>
```

Trigger printer beeper.

**Query Parameters:**
- `printer` (required) - Printer name
- `count` (optional) - Number of beeps 1-9 (default: `1`)
- `duration` (optional) - Duration in 100ms units 1-9 (default: `1`)

**Example:**
```bash
curl -H "X-API-Key: your_api_key_here" \
  "http://localhost:3006/beep?printer=TP80&count=3&duration=5"
```

---

### Cut Paper

```http
GET|POST /cut?printer=<printer_name>
```

Cut paper.

**Query Parameters:**
- `printer` (required) - Printer name
- `mode` (optional) - Cut mode: `partial` or `full` (default: `partial`)
- `feed` (optional) - Feed lines before cut (default: `3`)

**Example:**
```bash
curl -H "X-API-Key: your_api_key_here" \
  "http://localhost:3006/cut?printer=TP80&mode=full"
```

---

### Feed Paper

```http
GET|POST /feed?printer=<printer_name>
```

Feed paper lines.

**Query Parameters:**
- `printer` (required) - Printer name
- `lines` (optional) - Number of lines to feed (default: `3`)

**Example:**
```bash
curl -H "X-API-Key: your_api_key_here" \
  "http://localhost:3006/feed?printer=TP80&lines=5"
```

---

### Open Cash Drawer

```http
GET|POST /drawer?printer=<printer_name>
```

Send pulse to open cash drawer.

**Query Parameters:**
- `printer` (required) - Printer name
- `pin` (optional) - Pin number: `0` or `1` (default: `0`)
- `t1` (optional) - ON time in ms (default: `100`)
- `t2` (optional) - OFF time in ms (default: `100`)

**Example:**
```bash
curl -H "X-API-Key: your_api_key_here" \
  "http://localhost:3006/drawer?printer=TP80"
```

---

### Print Raw ESC/POS

```http
POST /print-raw?printer=<printer_name>
```

Send raw ESC/POS commands.

**Query Parameters:**
- `printer` (required) - Printer name

**Body (JSON):**
- `base64` - Base64 encoded data, OR
- `hex` - Hex encoded data

**Example:**
```bash
# Base64
curl -X POST "http://localhost:3006/print-raw?printer=TP80" \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"base64":"G0BA"}'

# Hex
curl -X POST "http://localhost:3006/print-raw?printer=TP80" \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"hex":"1B40"}'
```

---

## Configuration

Configuration is done via the `.env` file. See `.env.example` for all available options:

### **Required Settings:**
```env
SERVER_HOST=0.0.0.0              # Server host (0.0.0.0 = all interfaces)
SERVER_PORT=3006                 # Server port
API_KEY=your_api_key_here        # API key (generate with: openssl rand -hex 32)
```

### **Optional Settings:**
```env
# File uploads
UPLOAD_FOLDER=uploads            # Temporary upload folder
ALLOWED_EXTENSIONS=png,jpg,jpeg,bmp  # Allowed image types
MAX_UPLOAD_SIZE_MB=20            # Max upload size in MB

# Printer defaults
MAX_WIDTH_DEFAULT=576            # Default max width in pixels (80mm printer)
PRINT_SCRIPT=                    # Path to print_image_any.py (auto-detected)
```

The server automatically loads these settings on startup.

## Printer Setup

### List Available Printers

```bash
lpstat -p -d
```

### Add a Printer (Example)

```bash
lpadmin -p TP80 -E -v usb://path/to/printer
```

### Test Printer

```bash
echo "Test" | lp -d TP80
```

## Error Handling

All endpoints return JSON error responses:

```json
{
  "error": "Error message",
  "detail": "Additional details (if available)"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid or missing API key)
- `404` - Not Found (printer not found)
- `413` - Payload Too Large
- `500` - Server Error

## Development

### Project Structure

```
printers-manager/
├── server.py                    # FastAPI server (main application)
├── print_image_any.py           # Image to ESC/POS converter
├── requirements.txt             # Python dependencies
├── .env.example                 # Configuration template
├── .gitignore                   # Git ignore rules
├── README.md                    # This documentation
├── printers-bash/               # USB setup scripts
│   ├── usb_setup.sh            # Auto-setup script for Raspberry Pi
│   ├── USB_README.md           # USB setup documentation
│   └── .env.setup.example      # USB config template
├── .env                         # Your configuration (create from .env.example)
├── venv/                        # Virtual environment (created by you)
└── uploads/                     # Temporary uploads (auto-created)
```

### Testing

You can test all endpoints using the built-in Swagger UI at `http://localhost:3006/docs`

**Note:** You'll need to authorize with your API key in Swagger UI:
1. Click the "Authorize" button
2. Enter your API key in the `X-API-Key` field
3. Click "Authorize"

Or use curl/Postman/any HTTP client with the `X-API-Key` header.

## Migration from Flask

This server was converted from Flask to FastAPI. Key changes:

- ✅ Better performance with async support
- ✅ Automatic API documentation (Swagger/ReDoc)
- ✅ Built-in data validation with Pydantic
- ✅ Type hints and better IDE support
- ✅ Modern async/await patterns
- ✅ Better dependency injection

## Troubleshooting

### Printer Not Found

```bash
# Check if printer is available
lpstat -p

# Check printer status
lpstat -p your_printer_name
```

### Permission Denied

```bash
# Add user to lp group
sudo usermod -a -G lp $USER
```

### Image Printing Failed

Ensure `print_image_any.py` exists and is executable:

```bash
chmod +x print_image_any.py
```

## License

MIT License - Feel free to use and modify.

## Support

For issues or questions, please check the API documentation at `/docs` or review the error messages returned by the endpoints.

