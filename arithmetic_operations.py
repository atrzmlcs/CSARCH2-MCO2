import decimal

def encode_dpd(d1, d2, d3):
    """
    Converts 3 decimal digits into a 10-bit Densely Packed Decimal (DPD).
    """
    b1, b2, b3 = f"{d1:04b}", f"{d2:04b}", f"{d3:04b}"
    a, b, c, d = b1[0], b1[1], b1[2], b1[3]
    e, f, g, h = b2[0], b2[1], b2[2], b2[3]
    i, j, k, m = b3[0], b3[1], b3[2], b3[3]
    
    aei = a + e + i
    
    if aei == "000": return b+c+d + f+g+h + "0" + j+k+m
    elif aei == "001": return b+c+d + f+g+h + "100" + m
    elif aei == "010": return b+c+d + j+k+h + "101" + m
    elif aei == "011": return b+c+d + "10" + h + "111" + m
    elif aei == "100": return j+k+d + f+g+h + "110" + m
    elif aei == "101": return f+g+d + "01" + h + "111" + m
    elif aei == "110": return j+k+d + "00" + h + "111" + m
    elif aei == "111": return "00" + d + "11" + h + "111" + m

def decimal32_encode(base_str, exp_str="0"):
    print("\n--- BEGIN PARSING TRACE ---")
    
    base_lower = base_str.lower()
    if base_lower in ["infinity", "+infinity", "inf", "+inf"]:
        print("Trace: Positive Infinity detected.")
        return {"sign": "0", "comb": "11110", "exp_cont": "000000", "coeff_cont": "0000000000 0000000000"}
    if base_lower in ["-infinity", "-inf"]:
        print("Trace: Negative Infinity detected.")
        return {"sign": "1", "comb": "11110", "exp_cont": "000000", "coeff_cont": "0000000000 0000000000"}
    if base_lower == "nan":
        print("Trace: NaN (Not a Number) detected.")
        return {"sign": "0", "comb": "11111", "exp_cont": "000000", "coeff_cont": "0000000000 0000000000"}

    is_negative = False
    if base_str.startswith("-"):
        is_negative = True
        base_str = base_str[1:]
    elif base_str.startswith("+"):
        base_str = base_str[1:]
        
    sign_bit = "1" if is_negative else "0"
    print(f"Step 1: Check sign. Input is {'negative' if is_negative else 'positive'}, sign bit = {sign_bit}")
    
    if "." in base_str:
        left, right = base_str.split(".")
        whole_num = int(left + right)
        exp_shift = len(right)
        print(f"Step 2: Not a fully whole number. Shift radix right by {exp_shift}. Adjusted exponent: {exp_str} - {exp_shift} = {int(exp_str) - exp_shift}")
    else:
        whole_num = int(base_str)
        exp_shift = 0
        print(f"Step 2: Already a whole number. No radix shift needed.")
        
    final_exp = int(exp_str) - exp_shift
    digits_str = str(whole_num)

    # Cohort normalization to enforce E_max bounds
    if final_exp > 90:
        shifts = 0
        while final_exp > 90 and len(digits_str) < 7:
            whole_num *= 10
            final_exp -= 1
            digits_str = str(whole_num)
            shifts += 1
        if shifts > 0:
            print(f"Step 2b: Exponent exceeds max normal (90). Shift radix right {shifts} times -> {digits_str} x 10^{final_exp}")

    # Cohort normalization to salvage E_min underflows (stripping trailing zeros)
    if final_exp < -101:
        shifts = 0
        # Only shift if it divides perfectly by 10 (trailing zero)
        while final_exp < -101 and whole_num % 10 == 0 and whole_num != 0:
            whole_num //= 10
            final_exp += 1
            digits_str = str(whole_num)
            shifts += 1
        if shifts > 0:
            print(f"Step 2c: Exponent is below absolute min (-101). Shift radix left {shifts} times -> {digits_str} x 10^{final_exp}")
    
    if len(digits_str) > 7:
        raise ValueError("Error: Input exceeds the 7 significant digits limit.")
        
    padded_digits = digits_str.zfill(7)
    print(f"Step 3: Check if normalized to 7 whole digits. Pad leading 0's to the left: {padded_digits} x 10^{final_exp}")
    
    # Check bounds against absolute stored limits
    if final_exp > 90: 
        print("Trace: Exponent still exceeds max limit (90) after max radix shifts. Overflow to Infinity.")
        return {"sign": sign_bit, "comb": "11110", "exp_cont": "000000", "coeff_cont": "0000000000 0000000000"}
        
    if final_exp < -101:
        raise ValueError(f"Error: Adjusted exponent ({final_exp}) is below Decimal32 minimum bound (-101).")
    
    e_biased = final_exp + 101
    print(f"Step 4: Now normalized, get exponent representation: e = {final_exp} + 101 (bias) = {e_biased}")
    
    exp_bin = f"{e_biased:08b}"
    print(f"Step 5: Turn exponent representation ({e_biased}) into 8-bit binary = {exp_bin}")
    
    exp_2bits = exp_bin[0:2]
    print(f"Step 6: The 2 leftmost bits of the exponent ({exp_2bits}) will be used for combination field.")
    
    msd = int(padded_digits[0])
    msd_bin = f"{msd:04b}"
    print(f"Step 7: Identify most significant digit in {padded_digits} which is {msd}.")
    print(f"Step 8: Turn MSD into 4-bit binary = {msd_bin}.")
    
    if msd >= 0 and msd <= 7:
        comb_field = exp_2bits + msd_bin[-3:]
        print(f"Step 9: MSD is 0-7. Combination field (abcde): ab ({exp_2bits}) + cde ({msd_bin[-3:]}) = {comb_field}")
    else:
        comb_field = "11" + exp_2bits + msd_bin[-1:]
        print(f"Step 9: MSD is 8-9. Combination field (11cde): 11 + ab ({exp_2bits}) + e ({msd_bin[-1:]}) = {comb_field}")
        
    exp_cont = exp_bin[2:8]
    print(f"Step 10: Exponent continuation (6 remaining bits from exponent) = {exp_cont}")
    
    group1 = padded_digits[1:4]
    group2 = padded_digits[4:7]
    
    dpd1 = encode_dpd(int(group1[0]), int(group1[1]), int(group1[2]))
    dpd2 = encode_dpd(int(group2[0]), int(group2[1]), int(group2[2]))
    
    print(f"Step 11: Coefficient continuation (DPD of {group1} and {group2}):")
    print(f"         {group1} -> {dpd1}")
    print(f"         {group2} -> {dpd2}")
    print("--- END PARSING TRACE ---\n")
    
    coeff_cont = f"{dpd1} {dpd2}"
    
    return {
        "sign": sign_bit,
        "comb": comb_field,
        "exp_cont": exp_cont,
        "coeff_cont": coeff_cont
    }

# Configure the global decimal context for decimal32 limits
# Decimal32 has a precision of 7 decimal digits.
decimal.getcontext().prec = 7
decimal.getcontext().rounding = decimal.ROUND_HALF_EVEN

# --- HELPER FUNCTIONS (Integrate your Part 1 code here) ---

def decode_from_decimal32(hex_string):
    """
    Decodes an IEEE 754 decimal32 hex string into a Decimal object.
    You must insert your specific DPD or BID decoding logic here.
    """
    print(f"[*] Decoding IEEE Hex {hex_string} to Decimal...")
    # Placeholder: Assuming the logic returns a valid Decimal
    return decimal.Decimal('0') 

def encode_to_decimal32(dec_value):
    """
    Takes a Python Decimal object from Part 3's math output, extracts its 
    components, and feeds it into the Part 1 DPD encoder.
    """
    t = dec_value.as_tuple()
    
    # Handle IEEE 754 special cases
    if dec_value.is_infinite():
        base_str = "-inf" if t.sign else "inf"
        fields = decimal32_encode(base_str, "0")
    elif dec_value.is_nan():
        fields = decimal32_encode("nan", "0")
    else:
        # Reconstruct standard base string and exponent string from the tuple
        digits_str = "".join(str(d) for d in t.digits)
        sign_str = "-" if t.sign else ""
        
        # If the result is mathematically zero, normalize it
        if not digits_str or digits_str == "0":
            base_str = "0"
            exp_str = "0"
        else:
            base_str = sign_str + digits_str
            exp_str = str(t.exponent)

        # Feed the reconstructed strings into your Part 1 function
        fields = decimal32_encode(base_str, exp_str)
        
    # Reconstruct the spaced binary string and hex value from your dictionary
    binary_spaced = f"{fields['sign']} {fields['comb']} {fields['exp_cont']} {fields['coeff_cont']}"
    bin_solid = binary_spaced.replace(" ", "")
    hex_val = f"{int(bin_solid, 2):08X}"
    
    return binary_spaced, hex_val

# --- ARITHMETIC OPERATIONS (Part 3.b & 3.c) ---

def perform_subtraction(op1, op2):
    print("\n--- Step-by-Step Subtraction ---")
    
    t1 = op1.as_tuple()
    t2 = op2.as_tuple()
    
    exp1, exp2 = t1[2], t2[2] 
    
    print(f"Operand 1: {op1} (Exponent: {exp1})")
    print(f"Operand 2: {op2} (Exponent: {exp2})")
    
    target_exp = min(exp1, exp2)
    print(f"Step 1: Aligning exponents to the smaller value ({target_exp}).")
    
    result = op1 - op2
    
    print(f"Step 2: Subtracting coefficients.")
    print(f"Step 3: Applying rounding method ({decimal.getcontext().rounding}).")
    
    final_result = +result 
    print(f"Final Decimal Result: {final_result}")
    
    return final_result

def perform_division(op1, op2):
    print("\n--- Step-by-Step Division ---")
    
    if op2 == 0:
        print("Error: Division by zero.")
        return decimal.Decimal('Infinity')
        
    t1 = op1.as_tuple()
    t2 = op2.as_tuple()
    
    exp1, exp2 = t1[2], t2[2]
    
    print(f"Dividend: {op1} (Exponent: {exp1})")
    print(f"Divisor: {op2} (Exponent: {exp2})")
    
    new_exp = exp1 - exp2
    print(f"Step 1: Subtracting exponents ({exp1} - {exp2} = {new_exp}).")
    
    print(f"Step 2: Dividing coefficients.")
    print(f"Step 3: Applying rounding method ({decimal.getcontext().rounding}).")
    result = op1 / op2
    
    final_result = +result
    print(f"Final Decimal Result: {final_result}")
    
    return final_result

# --- MAIN EXECUTION ---

def main():
    print("--- IEEE 754 Decimal32 Calculator ---")
    
    # 1. Ask user for the operation
    operation = input("Will you use subtraction or division? (type 'sub' or 'div'): ").strip().lower()
    
    if operation not in ['sub', 'div']:
        print("Error: Invalid operation selected. Please restart and choose 'sub' or 'div'.")
        return
    
    print("\n--- Operand Format ---")
    # 2. Ask for the shared format for BOTH operands
    op_format = input("Will the operands be in Decimal or Hex? (type 'dec' or 'hex'): ").strip().lower()
    
    print("\n--- Inputs ---")
    # 3. Ask for the actual values
    op1_input = input("Enter Operand 1: ").strip()
    op2_input = input("Enter Operand 2: ").strip()
    
    # Parse BOTH operands based on the single format choice
    if op_format == 'hex':
        op1 = decode_from_decimal32(op1_input)
        op2 = decode_from_decimal32(op2_input)
    else:
        op1 = decimal.Decimal(op1_input)
        op2 = decimal.Decimal(op2_input)
    
    # 4. Do the task
    if operation == 'sub':
        final_decimal = perform_subtraction(op1, op2)
    elif operation == 'div':
        final_decimal = perform_division(op1, op2)
        
    # Final Output formatting (Part 3.c)
    spaced_bin, hex_out = encode_to_decimal32(final_decimal)
    
    print("\n--- Final Encoded Outputs ---")
    print(f"i) Decimal: {final_decimal}")
    print(f"ii) Binary: {spaced_bin}")
    print(f"iii) Hexadecimal: {hex_out}")

if __name__ == "__main__":
    main()