"""blob.py — a scene's data file: what its art tool made, for the program
to find in far memory.

    blob.write(out_dir, "village", streams=[("scene_pck", bytes), ...],
               tables=[("pal", "[89][3]", bytes), ("eave", "[320]", bytes), ...],
               defines=[("P_SNOW", 1), ...], comment="...")

writes <out_dir>/<name>.dat, the streams then the tables one after another,
and <name>.h:

    #define VILLAGE_SCENE_PCK  0x0000      the streams' offsets in the blob
    #define VILLAGE_TABLES     0x2A61      the tables' offset
    struct village_tables { unsigned char pal[89][3]; ... };   in this order
    #define VILLAGE_SIZE       ...         the blob's bytes

tools/data.py puts the blobs one after another in XMASDATA (loaded at the
program's start) and writes data.h: VILLAGE_LIN, where this blob is. A
scene copies its tables into a struct of this type (one DMA copy) and
unpacks its streams from where they are.
"""
import os


def write(out, name, streams, tables, defines=(), comment=""):
    up = name.upper()
    blob = bytearray()
    lines = ["/* %s.h — %s's data (tools/blob.py)%s */" % (name, name, (": " + comment) if comment else ""),
             "#pragma once", ""]
    for field, data in streams:
        lines.append("#define %-24s 0x%04X   /* %d bytes */" % (up + "_" + field.upper(), len(blob), len(data)))
        lines.append("#define %-24s %d" % (up + "_" + field.upper() + "_LEN", len(data)))
        blob += data
    lines.append("#define %-24s 0x%04X" % (up + "_TABLES", len(blob)))
    struct = ["struct %s_tables {" % name]
    size = 0
    for field, dims, data in tables:
        struct.append("    unsigned char %s%s;" % (field, dims))
        blob += bytes(data)
        size += len(data)
    struct.append("};")
    lines.append("#define %-24s %d" % (up + "_TABLES_SIZE", size))
    lines.append("#define %-24s %d" % (up + "_SIZE", len(blob)))
    lines.append("")
    for k, v in defines:
        lines.append("#define %-24s %s" % (k, v))
    lines.append("")
    lines += struct
    lines.append('_Static_assert(sizeof(struct %s_tables) == %s_TABLES_SIZE, "%s\'s tables");' % (name, up, name))
    with open(os.path.join(out, name + ".dat"), "wb") as f:
        f.write(blob)
    with open(os.path.join(out, name + ".h"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return len(blob)
