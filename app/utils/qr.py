import io
import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr_png_bytes(data: str) -> bytes:
    """Generate a QR code PNG for the given URL/string and return raw bytes."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
