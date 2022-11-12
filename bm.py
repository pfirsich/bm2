import sqlite3

import requests
import bs4

import db


def bookmark_url(cur: sqlite3.Cursor, folder_id: int, url: str) -> int:
    if not url.startswith("http://") or not url.startswith("https://"):
        url = "http://" + url
    req = requests.get(url)
    soup = bs4.BeautifulSoup(req.text, "html.parser")
    title = soup.find("title").get_text()
    return db.add_bookmark(cur, folder_id, title, url)


def main():
    con = sqlite3.connect("bm.sqlite")
    cur = con.cursor()

    with open("schema.sql") as f:
        cur.executescript(f.read())

    if len(db.list_entries(cur, "/")) == 0:
        a_id = db.add_folder(cur, 0, "a")
        bookmark_url(cur, a_id, "theshoemaker.de")
        aa_id = db.add_folder(cur, a_id, "aa")
        db.add_bookmark(cur, aa_id, "aa bookmark", "pfirsich.dev")

        b_id = db.add_folder(cur, 0, "b")
        db.add_bookmark(cur, b_id, "ab bookmark", "joelschumacher.de")

        c_id = db.add_folder(cur, 0, "c")
        db.add_bookmark(cur, b_id, "ab bookmark", "joelschumacher.de")
        db.remove_folder(cur, c_id)

    for e in db.list_entries(cur, "/a"):
        print(e)

    con.commit()
    con.close()


if __name__ == "__main__":
    main()
