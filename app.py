"""
app.py

Machine 4 - Decimal 32-bit Floating-Point web application.

Serves the GUI and exposes JSON API endpoints that wrap the three
computation modules:

  GET  /            -> the web app
  POST /api/encode  -> decimal32 IEEE 754 encoder (Part 1)
  POST /api/round   -> rounding methods (Part 2)
  POST /api/arith   -> subtraction / division (Part 3)
"""

import io
import contextlib
import re

from flask import Flask, jsonify, render_template, request

import decimal
import decimal32
import rounding
import arithmetic_operations as arith

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

_SPECIALS = {
    "infinity", "+infinity", "-infinity", "inf", "+inf", "-inf", "nan",
}
_BASE_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _capture(fn, *args, **kwargs):
    """Run a function while capturing its stdout as text."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = fn(*args, **kwargs)
    return result, buffer.getvalue()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/encode", methods=["POST"])
def api_encode():
    data = request.get_json(silent=True) or {}
    base = str(data.get("base", "")).strip()
    exp = str(data.get("exp", "")).strip()

    if not base:
        return jsonify({"ok": False, "error": "Please enter a decimal number."})

    if base.lower() not in _SPECIALS:
        if _BASE_PATTERN.fullmatch(base) is None:
            return jsonify({
                "ok": False,
                "error": "Invalid decimal number. Use digits, an optional sign, "
                         "and a single decimal point (scientific form like 1.5e3 is accepted).",
            })
        try:
            exp_value = "0" if exp == "" else str(int(exp))
        except ValueError:
            return jsonify({"ok": False, "error": "Exponent must be an integer."})

        if "e" in base.lower() or "E" in base:
            match = re.match(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))[eE]([+-]?\d+)$", base)
            base = match.group(1)
            exp_value = str(int(match.group(2)) + int(exp_value))
    else:
        exp_value = "0"

    try:
        fields, trace = _capture(decimal32.decimal32_encode, base, exp_value)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)})

    binary_spaced = (
        f"{fields['sign']} {fields['comb']} {fields['exp_cont']} "
        f"{fields['coeff_cont']}"
    )
    bin_solid = binary_spaced.replace(" ", "")
    hex_val = f"{int(bin_solid, 2):08X}"

    return jsonify(
        {
            "ok": True,
            "input": f"{base} x 10^{exp_value}",
            "fields": {
                "sign": fields["sign"],
                "combination": fields["comb"],
                "exponent_continuation": fields["exp_cont"],
                "coefficient_continuation": fields["coeff_cont"],
            },
            "binary": binary_spaced,
            "hex": "0x" + hex_val,
            "trace": trace,
        }
    )


@app.route("/api/round", methods=["POST"])
def api_round():
    data = request.get_json(silent=True) or {}
    value = str(data.get("value", "")).strip()
    input_type = str(data.get("input_type", "decimal")).strip().lower()
    target_text = str(data.get("target_digits", "")).strip()

    if input_type not in ("decimal", "binary"):
        return jsonify({"ok": False, "error": "Input type must be 'decimal' or 'binary'."})
    if not value:
        return jsonify({"ok": False, "error": "Please enter a number."})
    if not target_text.isdigit():
        return jsonify({"ok": False, "error": "Target digits must be a positive whole number."})

    try:
        result = rounding.calculate_all_rounding_methods(
            value=value,
            target_digits=int(target_text),
            input_type=input_type,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)})
    except decimal.InvalidOperation as exc:
        return jsonify({"ok": False, "error": f"Precision error: {exc}"})

    return jsonify(
        {
            "ok": True,
            "input_type": result.input_type,
            "original": result.original,
            "target_digits": result.target_digits,
            "chopping": result.chopping,
            "round_up": result.round_up,
            "round_down": result.round_down,
            "ties_to_even": result.ties_to_even,
            "explanation": result.explanation,
        }
    )


@app.route("/api/arith", methods=["POST"])
def api_arith():
    data = request.get_json(silent=True) or {}
    operation = str(data.get("operation", "sub")).strip().lower()
    fmt = str(data.get("format", "dec")).strip().lower()
    op1 = str(data.get("op1", "")).strip()
    op2 = str(data.get("op2", "")).strip()
    rounding_mode = str(data.get("rounding", "ties_to_even")).strip().lower()

    if not op1 or not op2:
        return jsonify({"ok": False, "error": "Please enter both operands."})
    if operation not in ("sub", "div"):
        return jsonify({"ok": False, "error": "Operation must be subtraction or division."})

    try:
        a, b = arith.parse_operands(op1, op2, fmt)
        payload = arith.compute(a, b, operation, rounding_mode)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)})

    return jsonify(payload)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
