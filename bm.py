import sqlite3

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, redirect, request

import db

app = Flask(__name__)


def bookmark_url(cur: sqlite3.Cursor, folder_id: int, url: str) -> int:
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    req = requests.get(url)
    soup = BeautifulSoup(req.text, "html.parser")
    title = soup.find("title").get_text()
    return db.add_bookmark(cur, folder_id, title, url)


@app.route("/")
def index():
    return redirect("/list")


@app.route("/list/", defaults={"path": ""})
@app.route("/list/<path:path>")
def list_entries(path):
    parts = [p for p in path.split("/") if p != ""]
    with db.Context() as cur:
        link = "/list/"
        breadcrumbs = [{"title": "/", "link": link}]
        for part in parts:
            link += part + "/"
            breadcrumbs.append({"title": f"{part}/", "link": link})
        entries = db.list_entries(cur, path)
        print(entries)
        return render_template(
            "base.html", path=path, entries=entries, breadcrumbs=breadcrumbs
        )


@app.route("/folders/", defaults={"path": ""}, methods=["POST"])
@app.route("/folders/<path:path>", methods=["POST"])
def post_folders(path):
    with db.Context() as cur:
        parent_id = db.get_folder_by_path(cur, path).folder_id
        db.add_folder(cur, parent_id, request.form["input"])
    return redirect(f"/list/{path}")


@app.route("/bookmarks/", defaults={"path": ""}, methods=["POST"])
@app.route("/bookmarks/<path:path>", methods=["POST"])
def post_bookmarks(path):
    with db.Context() as cur:
        folder_id = db.get_folder_by_path(cur, path).folder_id
        bookmark_url(cur, folder_id, request.form["input"])
    return redirect(f"/list/{path}")


@app.route("/folders/<int:folder_id>", methods=["DELETE"])
def delete_folders(folder_id):
    with db.Context() as cur:
        db.delete_folder(cur, folder_id)
    return ""


@app.route("/bookmarks/<int:bookmark_id>", methods=["DELETE"])
def delete_bookmarks(bookmark_id):
    with db.Context() as cur:
        db.delete_bookmark(cur, bookmark_id)
    return ""


def main():
    with db.Context() as cur:
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


if __name__ == "__main__":
    main()
