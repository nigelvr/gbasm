import sys
from opcodes import UNPREFIXED_OPCODES, PREFIXED_OPCODES

def clean(s):
    return s.split(';')[0].strip().replace("$","")

def replace_nemonic(line):
    if line == "XOR A":
        return "XOR A,A"
    split = line.split(" ")
    if len(split) == 2 and split[0] == "CP":
        return "CP " + "A," + split[1]
    if line == "ADD (HL)":
        return "ADD A,(HL)"
    if len(split) == 2 and split[0] == 'SUB':
        return "SUB A," + split[1]
    return line

def is_hex_str(s):
    for c in s:
        if c not in "0123456789ABCDEFabcdef":
            return False
    return True

def parse_line(line):
    immediate = list()
    if " " not in line:
        return line, immediate
    if line.startswith(".DB"):
        data = line.split(" ")[1].split(",")
        for d in data:
            immediate.append(int(d,16))
        return "", immediate
    args = line.split(" ")[1].split(",")
    for arg in args:
        if arg in ["A", "B", "C", "D", "E", "F", "H", "L", "SP", "PC"]: # a register
            continue
        elif arg in ["AF", "BC", "DE", "HL"]:
            continue
        elif len(arg) == 2 and is_hex_str(arg):
            if line.startswith("LD A"):
                line = line.replace(arg, "u8")
                immediate.append(int(arg, 16))
            elif "JR" in line or "ADD SP" in line or "LD HL" in line:
                line = line.replace(arg, "i8")
                immediate.append(int(arg, 16))
            else:
                line = line.replace(arg, "u8")
                immediate.append(int(arg, 16))
        elif len(arg) == 4 and is_hex_str(arg):
            # u16
            line = line.replace(arg, "u16")
            val = int(arg, 16)
            immediate.append(val & 0xFF)
            immediate.append((val >> 8) & 0xFF)
        elif arg == "(FF00+C)":
            pass
        elif arg in ["(BC)", "(DE)", "(HL)", "(HL-)", "(HL+)"]:
            pass
        elif arg.startswith("(FF00+") and arg[-1] == ")" and arg[6:-1].isdigit():
            line = line.replace(arg[6:-1], "u8")
            immediate.append(int(arg[6:-1], 16))
        elif arg.startswith("(") and arg.endswith(")") and is_hex_str(arg[1:-1]):
            line = line.replace(arg[1:-1], "u16")
            val = int(arg[1:-1], 16)
            immediate.append(val & 0xFF)
            immediate.append((val >> 8) & 0xFF)
        elif line.startswith("JR ") and ',' not in line:
            line = line.replace(arg, "i8")
            immediate.append(arg)
        elif (line.startswith("JR NZ") or line.startswith("JR Z") or line.startswith("JR NC") or line.startswith("JR C")) and (arg not in ["NZ", "Z", "NC", "C"]):
            line = line.replace(arg, "i8")
            immediate.append(arg)
    
    return line, immediate

def lookup_opdata(line):
    for k,I in enumerate(UNPREFIXED_OPCODES):
        if line == I["Name"]:
            return I | {"prefix": [], "opcode": k}
    for k,I in enumerate(PREFIXED_OPCODES):
        if line == I["Name"]:
            return I | {"prefix": [0xCB], "opcode": k}
    return {}

filename = ""
if len(sys.argv) != 2:
    print("Usage: python gbasm.py <filename>")
    sys.exit(1)
filename = sys.argv[1]

labels = dict()
code = dict()
pc = 0

# first pass
fd = open(filename, 'r')
for line in fd:
    label = ""
    line = replace_nemonic(clean(line))
    if line.isspace() or len(line) == 0:
        continue
    if ":" in line:
        label = line.rstrip(":")
        labels[label] = pc
        continue
    line, immediate = parse_line(line)
    opdata = lookup_opdata(line)
    if line == "": # this only happens when it's a .DB assembler command
        for x in immediate:
            code[pc] = {
                "line": ".DB",
                "immediate": [x]
            } | opdata
            pc += 1
    elif opdata:
        code[pc] = {
            "line": line,
            "immediate": immediate
        } | opdata
        pc += opdata["Length"]
    else:
        print("Unknown opcode for line:", line)

# 2nd pass: resolve labels
for addr in sorted(code.keys()):
    entry = code[addr]
    if len(entry["immediate"]) == 1 and entry["immediate"][0] in labels:
        value = entry["immediate"][0]
        target = labels[value]
        offset = target - (addr + entry["Length"])
        entry["immediate"] = [offset & 0xFF]


with open("./out.bin", "wb") as fd:
    for addr in sorted(code.keys()):
        entry = code[addr]
        if entry["line"] == ".DB":
            for x in entry["immediate"]:
                fd.write(bytes([x]))
        else:
            for b in entry["prefix"]:
                fd.write(bytes([b]))
            fd.write(bytes([entry["opcode"]]))
            fd.write(bytes(entry["immediate"]))
            