"""
arithmetic_operations.py

IEEE 754 decimal32 subtraction and division.

This module provides:
  - A full IEEE 754 decimal32 hex <-> Decimal decoder (DPD decoding)
  - Round-trip encoding of a Decimal result back to binary / hexadecimal
  - Step-by-step subtraction and division with configurable rounding
  - Reusable functions for the Machine 4 GUI and the terminal program
"""

import contextlib
import io
from decimal import (
    Decimal,
    DivisionByZero,
    InvalidOperation,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    getcontext,
)

from decimal32 import decimal32_encode

ROUNDING_MODE_NAMES = {
    "chopping": ROUND_DOWN,
    "round_up": ROUND_CEILING,
    "round_down": ROUND_FLOOR,
    "ties_to_even": ROUND_HALF_EVEN,
}

FRIENDLY_ROUNDING = {
    "chopping": "chopping (toward zero)",
    "round_up": "round up (toward +infinity)",
    "round_down": "round down (toward -infinity)",
    "ties_to_even": "round to nearest, ties to even",
}


# ---------------------------------------------------------------------------
# DPD decoding (IEEE 754 decimal32 -> Decimal)
# ---------------------------------------------------------------------------

def decode_dpd(bits):
    """
    Decode a 10-bit Densely Packed Decimal group into 3 decimal digits.
    This is the exact inverse of `encode_dpd` in decimal32.py.
    """
    if len(bits) != 10 or set(bits) - {"0", "1"}:
        raise ValueError("DPD group must be exactly 10 binary bits.")

    # Decision tree derived from the encoder's eight aei cases
    if bits[6] == "0":  # aei = 000
        return (int(bits[0:3], 2), int(bits[3:6], 2), int(bits[7:10], 2))
    if bits[7:9] == "00":  # aei = 001
        return (int(bits[0:3], 2), int(bits[3:6], 2), 8 + int(bits[9]))
    if bits[7:9] == "01":  # aei = 010
        return (int(bits[0:3], 2), 8 + int(bits[5]), int(bits[3:5] + bits[9], 2))
    if bits[7:9] == "10":  # aei = 100
        return (8 + int(bits[2]), int(bits[3:6], 2), int(bits[0:2] + bits[9], 2))

    # bits[7:9] == "11" -> aei is 011, 101, 110 or 111
    if bits[3:5] == "10":  # aei = 011
        return (int(bits[0:3], 2), 8 + int(bits[5]), 8 + int(bits[9]))
    if bits[3:5] == "01":  # aei = 101
        return (8 + int(bits[2]), int(bits[0:2] + bits[5], 2), 8 + int(bits[9]))
    if bits[3:5] == "00":  # aei = 110
        return (8 + int(bits[2]), 8 + int(bits[5]), int(bits[0:2] + bits[9], 2))
    return (8 + int(bits[2]), 8 + int(bits[5]), 8 + int(bits[9]))  # aei = 111


def decode_hex32(hex_str):
    """
    Decode an 8-digit IEEE 754 decimal32 hexadecimal string into a Decimal.
    Handles the combination field (MSD + 2 exponent bits), the 6-bit exponent
    continuation, and the two 10-bit DPD coefficient groups.
    """
    cleaned = str(hex_str).strip().replace("0x", "").replace("0X", "")
    if len(cleaned) != 8 or any(c not in "0123456789abcdefABCDEF" for c in cleaned):
        raise ValueError(
            f"Invalid decimal32 hex: {hex_str!r}. "
            "Expected exactly 8 hex digits, e.g. 22400525 or 0x22400525."
        )

    bits = f"{int(cleaned, 16):032b}"
    sign = bits[0]
    comb, exp_cont, coeff_cont = bits[1:6], bits[6:12], bits[12:32]

    # Special encodings: 11110* = Infinity, 11111* = NaN
    if comb[0:2] == "11" and comb[2:4] == "11":
        if comb[4] == "1":
            return Decimal("NaN")
        return Decimal("-Infinity") if sign == "1" else Decimal("Infinity")

    if comb[0:2] == "11":  # MSD is 8 or 9
        msd = 8 if comb[4] == "0" else 9
        exp_high2 = comb[2:4]
    else:  # MSD is 0-7, 4th MSD bit is implicit 0
        msd = int(comb[2:5], 2)
        exp_high2 = comb[0:2]

    exponent = int(exp_high2 + exp_cont, 2) - 101
    digits = (msd,) + decode_dpd(coeff_cont[0:10]) + decode_dpd(coeff_cont[10:20])
    return Decimal((int(sign), digits, exponent))


# ---------------------------------------------------------------------------
# Encoding back to binary / hexadecimal
# ---------------------------------------------------------------------------

def encode_to_decimal32(dec_value):
    """
    Encode a Decimal (result of an arithmetic operation) into the spaced
    binary form and the 8-digit hexadecimal form of a decimal32 number.
    """
    t = dec_value.as_tuple()

    if dec_value.is_infinite():
        base_str = "-inf" if t.sign else "inf"
        fields = decimal32_encode(base_str, "0")
    elif dec_value.is_nan():
        fields = decimal32_encode("nan", "0")
    elif dec_value.is_zero():
        fields = decimal32_encode("0", "0")
    else:
        digits_str = "".join(str(d) for d in t.digits)
        sign_str = "-" if t.sign else ""
        fields = decimal32_encode(sign_str + digits_str, str(t.exponent))

    binary_spaced = (
        f"{fields['sign']} {fields['comb']} {fields['exp_cont']} "
        f"{fields['coeff_cont']}"
    )
    bin_solid = binary_spaced.replace(" ", "")
    hex_val = f"{int(bin_solid, 2):08X}"
    return binary_spaced, hex_val


def format_decimal_value(value):
    """Human-friendly formatting for a Decimal result."""
    if value.is_infinite():
        return "Infinity" if value > 0 else "-Infinity"
    if value.is_nan():
        return "NaN"
    if value.is_zero():
        return "0"
    text = format(value, "f")
    if len(text) > 32:
        text = str(value)
    return text


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def parse_operands(op1, op2, operand_format):
    """Parse both operands given a shared format: 'decimal' or 'hex'."""
    fmt = str(operand_format).strip().lower()

    if fmt in ("hex", "hexadecimal", "ieee", "ieee hex"):
        return decode_hex32(op1), decode_hex32(op2)
    if fmt in ("dec", "decimal"):
        try:
            return Decimal(op1), Decimal(op2)
        except InvalidOperation as exc:
            raise ValueError(
                "One of the operands is not a valid decimal number."
            ) from exc
    raise ValueError("Operand format must be 'decimal' or 'hex'.")


# ---------------------------------------------------------------------------
# Arithmetic operations (step-by-step)
# ---------------------------------------------------------------------------

def _apply_context(rounding_mode):
    getcontext().prec = 7
    getcontext().rounding = ROUNDING_MODE_NAMES.get(rounding_mode, ROUND_HALF_EVEN)


def perform_subtraction(op1, op2, rounding_mode="ties_to_even"):
    print("--- Step-by-step subtraction ---")

    if op1.is_nan() or op2.is_nan():
        print("An operand is NaN. The result is NaN (invalid operation).")
        return Decimal("NaN")

    print(f"Operand 1 : {format_decimal_value(op1)}")
    print(f"Operand 2 : {format_decimal_value(op2)}")

    if op1.is_infinite() or op2.is_infinite():
        if op1.is_infinite() and op2.is_infinite() and (op1 > 0) == (op2 > 0):
            print("Step 1: Infinity - Infinity is undefined. The result is NaN.")
            return Decimal("NaN")
        result = op1 if op1.is_infinite() else op2
        print("Step 1: An infinity operand is present; the result carries its sign.")
        print(f"Step 2: Applying rounding method ({FRIENDLY_ROUNDING[rounding_mode]}).")
        return result

    exp1, exp2 = op1.as_tuple().exponent, op2.as_tuple().exponent
    target_exp = min(exp1, exp2)
    print(f"Step 1: Aligning exponents to the smaller value (10^{target_exp}).")
    print("Step 2: Subtracting coefficients.")
    print(
        f"Step 3: Applying rounding method ({FRIENDLY_ROUNDING[rounding_mode]}) "
        "at 7 significant digits."
    )

    try:
        result = op1 - op2
    except InvalidOperation:
        return Decimal("NaN")

    return +result


def perform_division(op1, op2, rounding_mode="ties_to_even"):
    print("--- Step-by-step division ---")

    if op1.is_nan() or op2.is_nan():
        print("An operand is NaN. The result is NaN (invalid operation).")
        return Decimal("NaN")

    print(f"Dividend : {format_decimal_value(op1)}")
    print(f"Divisor  : {format_decimal_value(op2)}")

    if op2.is_zero():
        if op1.is_zero():
            print("Step 1: 0 / 0 is undefined. The result is NaN.")
            return Decimal("NaN")
        negative = op1.is_signed() != op2.is_signed()
        print("Step 1: Division by zero detected.")
        print(f"Step 2: The result is {('-' if negative else '')}Infinity.")
        return Decimal("-Infinity") if negative else Decimal("Infinity")

    if op1.is_infinite() and op2.is_infinite():
        print("Step 1: Infinity / Infinity is undefined. The result is NaN.")
        return Decimal("NaN")

    if op1.is_infinite():
        negative = op1.is_signed() != op2.is_signed()
        print("Step 1: An infinite dividend is divided by a finite divisor.")
        print(f"Step 2: The result is {('-' if negative else '')}Infinity.")
        return Decimal("-Infinity") if negative else Decimal("Infinity")

    if op2.is_infinite():
        negative = op1.is_signed() != op2.is_signed()
        print("Step 1: A finite dividend is divided by an infinite divisor.")
        print(f"Step 2: The result is {('-' if negative else '')}0.")
        return Decimal("-0") if negative else Decimal("0")

    exp1, exp2 = op1.as_tuple().exponent, op2.as_tuple().exponent
    new_exp = exp1 - exp2
    print(f"Step 1: Subtracting exponents ({exp1} - {exp2} = {new_exp}).")
    print("Step 2: Dividing coefficients.")
    print(
        f"Step 3: Applying rounding method ({FRIENDLY_ROUNDING[rounding_mode]}) "
        "at 7 significant digits."
    )

    try:
        result = op1 / op2
    except (InvalidOperation, DivisionByZero):
        return Decimal("NaN")

    return +result


def compute(op1, op2, operation, rounding_mode="ties_to_even"):
    """
    Run a subtraction or division and return a result dictionary suitable for
    both the terminal and the GUI.

    Returns:
        {
            "ok": True,
            "operation": "subtraction" | "division",
            "rounding": <friendly rounding name>,
            "steps": <step-by-step text>,
            "decimal": <final decimal value>,
            "binary": <spaced binary form> | None,
            "hex": <hexadecimal form> | None,
            "special": "inf" | "nan" | "zero" | None,
            "encoding_note": <message if binary/hex could not be produced>
        }
    """
    op = str(operation).strip().lower()
    if op not in ("sub", "div"):
        raise ValueError("Operation must be 'sub' (subtraction) or 'div' (division).")
    if rounding_mode not in FRIENDLY_ROUNDING:
        rounding_mode = "ties_to_even"

    _apply_context(rounding_mode)

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        if op == "sub":
            result = perform_subtraction(op1, op2, rounding_mode)
        else:
            result = perform_division(op1, op2, rounding_mode)
    steps = buffer.getvalue()

    special = None
    if result.is_infinite():
        special = "inf"
    elif result.is_nan():
        special = "nan"
    elif result.is_zero():
        special = "zero"

    binary = hex_out = None
    encoding_note = ""
    encode_trace = ""
    try:
        enc_buffer = io.StringIO()
        with contextlib.redirect_stdout(enc_buffer):
            binary, hex_out = encode_to_decimal32(result)
        encode_trace = enc_buffer.getvalue()
        hex_out = "0x" + hex_out
    except ValueError as exc:
        encoding_note = str(exc)

    return {
        "ok": True,
        "operation": "subtraction" if op == "sub" else "division",
        "rounding": FRIENDLY_ROUNDING[rounding_mode],
        "steps": steps,
        "encode_trace": encode_trace,
        "decimal": format_decimal_value(result),
        "binary": binary,
        "hex": hex_out,
        "special": special,
        "encoding_note": encoding_note,
    }


# ---------------------------------------------------------------------------
# Terminal entry point
# ---------------------------------------------------------------------------

def main():
    print("--- IEEE 754 Decimal32 Calculator ---")

    operation = input(
        "Will you use subtraction or division? (type 'sub' or 'div'): "
    ).strip().lower()
    if operation not in ("sub", "div"):
        print("Error: Invalid operation selected. Please restart and choose 'sub' or 'div'.")
        return

    op_format = input(
        "Will the operands be in Decimal or Hex? (type 'dec' or 'hex'): "
    ).strip().lower()

    rounding_mode = input(
        "Rounding method (ties_to_even / chopping / round_up / round_down): "
    ).strip().lower()

    op1_input = input("Enter Operand 1: ").strip()
    op2_input = input("Enter Operand 2: ").strip()

    try:
        op1, op2 = parse_operands(op1_input, op2_input, op_format)
    except ValueError as error:
        print(f"\nError: {error}")
        return

    result = compute(op1, op2, operation, rounding_mode)

    print()
    print(result["steps"])
    print()
    print("--- Final Encoded Outputs ---")
    print(f"i)  Decimal      : {result['decimal']}")
    print(f"ii) Binary       : {result['binary'] or 'unavailable'}")
    print(f"iii) Hexadecimal : {result['hex'] or 'unavailable'}")
    if result["encoding_note"]:
        print(f"Note: {result['encoding_note']}")


if __name__ == "__main__":
    main()
