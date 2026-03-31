import sys
from extractor import extract_text_blocks
from structure import group_paragraphs
from diff_engine import compute_diff, save_html

def run(pdf1, pdf2):
    blocks1 = extract_text_blocks(pdf1)
    blocks2 = extract_text_blocks(pdf2)

    para1 = group_paragraphs(blocks1)
    para2 = group_paragraphs(blocks2)

    diff = compute_diff(para1, para2)

    for line in diff:
        print(line)

    save_html(diff)
    print("\nHTML output saved as diff_output.html")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python main.py file1.pdf file2.pdf")
    else:
        run(sys.argv[1], sys.argv[2])
