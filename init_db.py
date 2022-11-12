import db


def main():
    with db.Context() as cur:
        with open("schema.sql") as f:
            cur.executescript(f.read())

        if len(db.list_entries(cur, "/")) == 0:
            a_id = db.add_folder(cur, 0, "a")
            db.add_bookmark(cur, a_id, "a bookmark", "theshoemaker.de")
            aa_id = db.add_folder(cur, a_id, "aa")
            db.add_bookmark(cur, aa_id, "aa bookmark", "pfirsich.dev")

            b_id = db.add_folder(cur, 0, "b")
            db.add_bookmark(cur, b_id, "ab bookmark", "joelschumacher.de")

            c_id = db.add_folder(cur, 0, "c")
            db.add_bookmark(cur, b_id, "ab bookmark", "joelschumacher.de")
            db.delete_folder(cur, c_id)

        for e in db.list_entries(cur, "/a"):
            print(e)


if __name__ == "__main__":
    main()
