import sqlite3
from dataclasses import dataclass


@dataclass
class Bookmark:
    bookmark_id: int
    folder_id: int
    title: str
    url: str
    comment: str


@dataclass
class Folder:
    folder_id: int
    parent_id: int | None
    title: str


root_folder = Folder(0, None, "")


con = sqlite3.connect("bm.sqlite")
cur = con.cursor()


def reassign_sort_keys(parent_id: int):
    pass


def get_last_sort_key(parent_id: int) -> int:
    res = cur.execute(
        """
        SELECT ifnull(m + 1, 0) FROM (
            SELECT MAX(sort_key) AS m FROM (
                SELECT sort_key FROM folders_order AS fo INNER JOIN folders AS f ON f.folder_id = fo.folder_id WHERE f.parent_id = ?
                UNION ALL
                SELECT sort_key FROM bookmarks_order AS bo INNER JOIN bookmarks as b ON b.bookmark_id = bo.bookmark_id WHERE b.folder_id = ?
            )
        )
        """,
        (parent_id, parent_id),
    )
    return res.fetchone()[0]


def move_folder_to_bottom(folder_id: int, parent_id: int):
    # Doing this in two statements is kind of racey, but doing it in one statement
    # would require duplicating the SELECT in get_last_sort_key.
    # We also need that SELECT for move_bookmark_to_bottom and reusing that is also nice.
    sort_key = get_last_sort_key(parent_id)
    cur.execute(
        """
        INSERT INTO folders_order(folder_id, sort_key)
            VALUES (?, ?)
            ON CONFLICT (folder_id)
            DO UPDATE SET sort_key = ?;
        """,
        (folder_id, sort_key, sort_key),
    )


def add_folder(parent_id: int, title: str) -> int:
    cur.execute(
        "INSERT INTO folders(parent_id, title) VALUES(?, ?);",
        (parent_id, title),
    )
    folder_id = cur.lastrowid
    move_folder_to_bottom(folder_id, parent_id)
    return folder_id


def get_folder(folder_id: int) -> Folder:
    res = cur.execute(
        "SELECT parent_id, title FROM folders WHERE folder_id = ?;", (folder_id,)
    )
    row = res.fetchone()
    if row is None:
        raise ValueError("folder_id does not exist")
    return Folder(folder_id, row[0], row[1])


def get_folder_by_path(path: str) -> Folder:
    # After writing the folders_order insert in add_folder, I don't want to do this with SQLite.
    # Note that this works with redundant slashes, empty strings, "/", etc.
    parts = [p for p in path.split("/") if p != ""]
    cur_id = root_folder.folder_id
    for part in parts:
        res = cur.execute(
            "SELECT folder_id FROM folders WHERE title = ? AND parent_id = ?;",
            (part, cur_id),
        )
        row = res.fetchone()
        if row is None:
            raise ValueError("Path does not exist")
        cur_id = row[0]
    return get_folder(cur_id)


def update_folder(folder: Folder):
    cur.execute(
        "UPDATE folders SET parent_id = ?, title = ? WHERE folder_id = ?;",
        (folder.parent_id, folder.title, folder.folder_id),
    )


def remove_folder(folder_id: int):
    res = cur.execute(
        "SELECT bookmark_id FROM bookmarks WHERE folder_id = ?;", (folder_id,)
    )
    for row in res.fetchall():
        remove_bookmark(row[0])
    cur.execute("DELETE FROM folders_order WHERE folder_id = ?;", (folder_id,))
    cur.execute("DELETE FROM folders WHERE folder_id = ?;", (folder_id,))


def move_bookmark_to_bottom(bookmark_id: int, folder_id: int):
    sort_key = get_last_sort_key(folder_id)
    cur.execute(
        """
        INSERT INTO bookmarks_order(bookmark_id, sort_key)
            VALUES (?, ?)
            ON CONFLICT (bookmark_id)
            DO UPDATE SET sort_key = ?;
        """,
        (bookmark_id, sort_key, sort_key),
    )


def add_bookmark(folder_id: int, title: str, url: str) -> int:
    cur.execute(
        "INSERT INTO bookmarks(folder_id, title, url) VALUES(?, ?, ?);",
        (folder_id, title, url),
    )
    bookmark_id = cur.lastrowid
    move_bookmark_to_bottom(bookmark_id, folder_id)
    return bookmark_id


def get_bookmark(bookmark_id: int) -> Bookmark:
    res = cur.execute(
        "SELECT folder_id, title, url, comment FROM bookmarks WHERE bookmark_id = ?;",
        (bookmark_id,),
    )
    row = res.fetchone()
    if row is None:
        raise ValueError("bookmark_id does not exist")
    return Bookmark(bookmark_id, row[0], row[1], row[2], row[3])


def update_bookmark(bookmark: Bookmark):
    cur.execute(
        "UPDATE bookmarks SET folder_id = ?, title = ?, url = ?, comment = ? WHERE bookmark_id = ?;",
        (
            bookmark.folder_id,
            bookmark.title,
            bookmark.url,
            bookmark.comment,
            bookmark.bookmark_id,
        ),
    )


def remove_bookmark(bookmark_id: int):
    cur.execute("DELETE FROM bookmarks_order WHERE bookmark_id = ?;", (bookmark_id,))
    cur.execute("DELETE FROM bookmarks WHERE bookmark_id = ?;", (bookmark_id,))


##################################################################


def list_entries(path: str, folders_first: bool = True) -> list[Folder | Bookmark]:
    folder_id = get_folder_by_path(path).folder_id

    fres = cur.execute(
        """
        SELECT f.folder_id, title, sort_key FROM folders AS f
            INNER JOIN folders_order AS fo ON f.folder_id = fo.folder_id
            WHERE parent_id = ?;
        """,
        (folder_id,),
    )
    entries = [(row[2], Folder(row[0], folder_id, row[1])) for row in fres.fetchall()]

    bres = cur.execute(
        """
        SELECT b.bookmark_id, title, url, comment, sort_key FROM bookmarks AS b
            INNER JOIN bookmarks_order AS bo ON b.bookmark_id = bo.bookmark_id
            WHERE folder_id = ?;
        """,
        (folder_id,),
    )
    entries.extend(
        (row[4], Bookmark(row[0], folder_id, row[1], row[2], row[3]))
        for row in bres.fetchall()
    )

    entries.sort(key=lambda e: e[0])
    return [e[1] for e in entries]


import requests
import bs4


def bookmark_url(folder_id: int, url: str) -> Bookmark:
    if not url.startswith("http://") or not url.startswith("https://"):
        url = "http://" + url
    req = requests.get(url)
    soup = bs4.BeautifulSoup(req.text, "html.parser")
    title = soup.find("title").get_text()
    bookmark_id = add_bookmark(folder_id, title, url)
    return Bookmark(bookmark_id, folder_id, title, url, "")


def main():
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS folders(
            folder_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            title TEXT NOT NULL,

            FOREIGN KEY(parent_id) REFERENCES folders(folder_id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS folders_order(
            folder_id INTEGER PRIMARY KEY,
            sort_key INTEGER,

            FOREIGN KEY(folder_id) REFERENCES folders(folder_id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bookmarks(
            bookmark_id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            comment TEXT,

            FOREIGN KEY(folder_id) REFERENCES folders(folder_id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bookmarks_order(
            bookmark_id INTEGER PRIMARY KEY,
            sort_key INTEGER,

            FOREIGN KEY(bookmark_id) REFERENCES bookmarks(bookmark_id)
        );
        """
    )

    # Make sure root directory exists
    cur.execute(
        'INSERT OR IGNORE INTO folders(folder_id, parent_id, title) VALUES(0, NULL, "");'
    )

    if len(list_entries("/")) == 0:
        a_id = add_folder(0, "a")
        bookmark_url(a_id, "theshoemaker.de")
        aa_id = add_folder(a_id, "aa")
        add_bookmark(aa_id, "aa bookmark", "pfirsich.dev")

        b_id = add_folder(0, "b")
        add_bookmark(b_id, "ab bookmark", "joelschumacher.de")

        c_id = add_folder(0, "c")
        add_bookmark(b_id, "ab bookmark", "joelschumacher.de")
        remove_folder(c_id)

    for e in list_entries("/a"):
        print(e)

    con.commit()
    con.close()


if __name__ == "__main__":
    main()
