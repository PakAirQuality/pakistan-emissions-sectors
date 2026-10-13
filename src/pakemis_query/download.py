"""download_query_result: the rows behind an envelope as canonical CSV plus RECEIPT.json.

The download restates the receipt and every provenance digest; when any stream in scope is
ODbL-licensed the receipt carries the OpenStreetMap attribution block, because an extracted
table is a database under ODbL even when the map above it was a produced work."""
import csv
import io
import json

ODBL = ("Contains information from OpenStreetMap (c) OpenStreetMap contributors, ODbL 1.0. "
        "The road-density, building-fraction, rail and landfill tables are derivative databases "
        "under ODbL; a produced work (a rendered map) needs attribution only.")


def result_csv(env):
    rows = env["values"]
    fields = ["display", "exact", "unit", "formula", "result_row_ids"]
    extra = sorted({k for r in rows for k in r if k not in fields and k != "value"})
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields + extra, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        row = dict(r)
        row["result_row_ids"] = ";".join(r.get("result_row_ids", []))
        for k in extra:
            if isinstance(row.get(k), (dict, list)):
                row[k] = json.dumps(row[k], sort_keys=True)
        writer.writerow(row)
    return buf.getvalue()


def receipt_json(env, odbl_in_scope=False):
    body = {"receipt": env["receipt"], "request": env["request"], "request_type": env["request_type"],
            "context": env["context"], "provenance": env["provenance"], "result_sha256": env["result_sha256"],
            "citation": env["citation"], "licence": "CC-BY-4.0 (data); the ODbL note applies where stated"}
    if odbl_in_scope:
        body["odbl_attribution"] = ODBL
    return json.dumps(body, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
