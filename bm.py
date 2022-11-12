import sqlite3
from urllib.parse import urlparse, ParseResult
import base64

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, redirect, request

import db

app = Flask(__name__)


def get_favicon_data(base_url: ParseResult, soup: BeautifulSoup) -> str:
    favicon = soup.find("link", rel="shortcut icon")
    if favicon is None:
        favicon = soup.find("link", rel="icon")
    if favicon is None:
        favicon_url = f"{base_url.scheme}://{base_url.netloc}/favicon.ico"
    else:
        favicon_url = favicon["href"]
        parsed_favicon_url = urlparse(favicon_url)
        if parsed_favicon_url.scheme == "":
            if favicon_url.startswith("/"):
                favicon_url = f"{base_url.scheme}://{base_url.netloc}{favicon_url}"
            else:
                raise NotImplemented("Implement relative url")

    if favicon_url.startswith("data:"):
        return favicon_url
    else:
        favicon_req = requests.get(favicon_url, allow_redirects=True)
        if favicon_req.status_code // 100 == 2:
            return (
                f"data:{favicon_req.headers['content-type']};base64,"
                + base64.b64encode(favicon_req.content).decode("utf-8")
            )

    return None


def bookmark_url(cur: sqlite3.Cursor, folder_id: int, url: str) -> int:
    parsed_url = urlparse(url)
    if parsed_url.scheme == "":
        url = "http://" + url
        parsed_url = urlparse(url)
    req = requests.get(url)

    soup = BeautifulSoup(req.text, "html.parser")

    title = soup.find("title").get_text()
    favicon_data = get_favicon_data(parsed_url, soup)
    if not favicon_data is None:
        favicon_id = db.add_favicon(cur, favicon_data)
    else:
        favicon_id = None

    return db.add_bookmark(cur, folder_id, title, url, favicon_id)


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
