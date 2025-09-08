import json, re, sys, pathlib
in_path = pathlib.Path(sys.argv[1])
out_jsonl = pathlib.Path(sys.argv[2])
refs_dir = pathlib.Path(sys.argv[3])

def slug(s): return re.sub(r"[^a-z0-9]+","-", s.lower()).strip("-")[:60]

data = json.loads(in_path.read_text(encoding="utf-8"))
items = []
refs_dir.mkdir(parents=True, exist_ok=True)
count = 0
for article in data["data"]:
    title = article.get("title","article")
    for para_idx, para in enumerate(article["paragraphs"]):
        ctx = para["context"]
        for qa in para["qas"]:
            if count >= 50: break
            qid = qa["id"]; q = qa["question"]
            ans = qa["answers"][0]["text"] if qa.get("answers") else ""
            ref_name = f"{slug(title)}-p{para_idx}-{slug(qid)}.txt"
            (refs_dir / ref_name).write_text(ctx, encoding="utf-8")
            items.append({
                "id": qid,
                "input": q,
                "expected": ans,
                "context_url": f"{refs_dir.as_posix()}/{ref_name}",
                "tags": {"dataset":"SQuADv1.1-dev"}
            })
            count += 1
        if count >= 50: break
    if count >= 50: break

out_jsonl.parent.mkdir(parents=True, exist_ok=True)
with out_jsonl.open("w", encoding="utf-8") as f:
    for it in items: f.write(json.dumps(it, ensure_ascii=False) + "\n")
print("Wrote", out_jsonl.as_posix(), "items:", len(items))
print("Refs:", refs_dir.as_posix())
