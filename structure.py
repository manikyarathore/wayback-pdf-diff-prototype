def group_paragraphs(blocks):
    blocks = sorted(blocks, key=lambda x: (x["page"], x["y"]))

    paragraphs = []
    current = ""

    for b in blocks:
        text = b["text"]

        if len(text) < 50:
            current += " " + text
        else:
            if current:
                paragraphs.append(current.strip())
            current = text

    if current:
        paragraphs.append(current.strip())

    return paragraphs

