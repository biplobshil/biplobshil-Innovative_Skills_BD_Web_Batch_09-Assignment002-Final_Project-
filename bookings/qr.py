"""QR code images for tickets. Generated on request, never stored."""

import base64
import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def qr_png(data: str) -> bytes:
    code = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=4)
    code.add_data(data)
    code.make(fit=True)
    buffer = io.BytesIO()
    code.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def qr_data_uri(data: str) -> str:
    return "data:image/png;base64," + base64.b64encode(qr_png(data)).decode()