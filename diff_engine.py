import difflib

def compute_diff(paragraphs_a, paragraphs_b):
    diff = difflib.unified_diff(
        paragraphs_a,
        paragraphs_b,
        lineterm=""
    )
    return list(diff)


def save_html(diff, output="diff_output.html"):
    with open(output, "w") as f:
        f.write("<pre>")
        for line in diff:
            if line.startswith("+"):
                f.write(f"<span style='color:green'>{line}</span>\n")
            elif line.startswith("-"):
                f.write(f"<span style='color:red'>{line}</span>\n")
            else:
                f.write(line + "\n")
        f.write("</pre>")
