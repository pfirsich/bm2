import sqlite3
from dataclasses import dataclass


@dataclass
class Bookmark:
    bookmark_id: int
    folder_id: int
    title: str
    url: str
    comment: str
    favicon_data_url: str


@dataclass
class Folder:
    folder_id: int
    parent_id: int | None
    title: str


root_folder = Folder(0, None, "")


class Context:
    def __enter__(self):
        self.conn = sqlite3.connect("bm.sqlite")
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.commit()
        self.conn.close()


def reassign_sort_keys(parent_id: int):
    pass


def get_last_sort_key(cur: sqlite3.Cursor, parent_id: int) -> int:
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


def move_folder_to_bottom(cur: sqlite3.Cursor, folder_id: int, parent_id: int):
    # Doing this in two statements is kind of racey, but doing it in one statement
    # would require duplicating the SELECT in get_last_sort_key.
    # We also need that SELECT for move_bookmark_to_bottom and reusing that is also nice.
    sort_key = get_last_sort_key(cur, parent_id)
    cur.execute(
        """
        INSERT INTO folders_order(folder_id, sort_key)
            VALUES (?, ?)
            ON CONFLICT (folder_id)
            DO UPDATE SET sort_key = ?;
        """,
        (folder_id, sort_key, sort_key),
    )


def add_folder(cur: sqlite3.Cursor, parent_id: int, title: str) -> int:
    cur.execute(
        "INSERT INTO folders(parent_id, title) VALUES(?, ?);",
        (parent_id, title),
    )
    folder_id = cur.lastrowid
    move_folder_to_bottom(cur, folder_id, parent_id)
    return folder_id


def get_folder(cur: sqlite3.Cursor, folder_id: int) -> Folder:
    res = cur.execute(
        "SELECT parent_id, title FROM folders WHERE folder_id = ?;", (folder_id,)
    )
    row = res.fetchone()
    if row is None:
        raise ValueError("folder_id does not exist")
    return Folder(folder_id, row[0], row[1])


def get_folder_by_path(cur: sqlite3.Cursor, path: str) -> Folder:
    # After writing the folders_order insert in add_folder, I don't want to do this with SQLite.
    # Note that this works with redundant slashes, empty strings, "/", etc.
    parts = [p for p in path.split("/") if p != ""]
    current_folder_id = root_folder.folder_id
    for part in parts:
        res = cur.execute(
            "SELECT folder_id FROM folders WHERE title = ? AND parent_id = ?;",
            (part, current_folder_id),
        )
        row = res.fetchone()
        if row is None:
            raise ValueError("Path does not exist")
        current_folder_id = row[0]
    return get_folder(cur, current_folder_id)


def update_folder(cur: sqlite3.Cursor, folder: Folder):
    cur.execute(
        "UPDATE folders SET parent_id = ?, title = ? WHERE folder_id = ?;",
        (folder.parent_id, folder.title, folder.folder_id),
    )


def delete_folder(cur: sqlite3.Cursor, folder_id: int):
    res = cur.execute(
        "SELECT bookmark_id FROM bookmarks WHERE folder_id = ?;", (folder_id,)
    )
    for row in res.fetchall():
        delete_bookmark(cur, row[0])
    cur.execute("DELETE FROM folders_order WHERE folder_id = ?;", (folder_id,))
    cur.execute("DELETE FROM folders WHERE folder_id = ?;", (folder_id,))


def add_favicon(cur: sqlite3.Cursor, data_url: str) -> int:
    cur.execute("INSERT INTO favicons(data_url) VALUES (?);", (data_url,))
    return cur.lastrowid


def move_bookmark_to_bottom(cur: sqlite3.Cursor, bookmark_id: int, folder_id: int):
    sort_key = get_last_sort_key(cur, folder_id)
    cur.execute(
        """
        INSERT INTO bookmarks_order(bookmark_id, sort_key)
            VALUES (?, ?)
            ON CONFLICT (bookmark_id)
            DO UPDATE SET sort_key = ?;
        """,
        (bookmark_id, sort_key, sort_key),
    )


def add_bookmark(
    cur: sqlite3.Cursor, folder_id: int, title: str, url: str, favicon_id: int = None
) -> int:
    cur.execute(
        "INSERT INTO bookmarks(folder_id, title, url, comment, favicon_id) VALUES(?, ?, ?, '', ?);",
        (folder_id, title, url, favicon_id),
    )
    bookmark_id = cur.lastrowid
    move_bookmark_to_bottom(cur, bookmark_id, folder_id)
    return bookmark_id


def get_favicon(cur: sqlite3.Cursor, favicon_id: int | None) -> int | None:
    if favicon_id is None:
        return None
    fres = cur.execute(
        "SELECT data_url FROM favicons WHERE favicon_id = ?;", (favicon_id,)
    )
    return fres.fetchone()[0]


def get_bookmark(cur: sqlite3.Cursor, bookmark_id: int) -> Bookmark:
    res = cur.execute(
        "SELECT folder_id, title, url, comment, favicon_id FROM bookmarks WHERE bookmark_id = ?;",
        (bookmark_id,),
    )
    row = res.fetchone()
    if row is None:
        raise ValueError("bookmark_id does not exist")
    return Bookmark(
        bookmark_id, row[0], row[1], row[2], row[3], get_favicon(cur, row[4])
    )


def update_bookmark(cur: sqlite3.Cursor, bookmark: Bookmark):
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


def delete_bookmark(cur: sqlite3.Cursor, bookmark_id: int):
    cur.execute("DELETE FROM bookmarks_order WHERE bookmark_id = ?;", (bookmark_id,))
    cur.execute("DELETE FROM bookmarks WHERE bookmark_id = ?;", (bookmark_id,))


def list_entries(
    cur: sqlite3.Cursor, path: str, folders_first: bool = True
) -> list[Folder | Bookmark]:
    folder_id = get_folder_by_path(cur, path).folder_id

    fres = cur.execute(
        """
        SELECT f.folder_id, title, sort_key FROM folders AS f
            INNER JOIN folders_order AS fo ON f.folder_id = fo.folder_id
            WHERE parent_id = ?;
        """,
        (folder_id,),
    )
    entries = [(row[2], Folder(row[0], folder_id, row[1])) for row in fres.fetchall()]

    if folders_first:
        entries.sort(key=lambda e: e[0])

    bres = cur.execute(
        """
        SELECT b.bookmark_id, title, url, comment, favicon_id, sort_key FROM bookmarks AS b
            INNER JOIN bookmarks_order AS bo ON b.bookmark_id = bo.bookmark_id
            WHERE folder_id = ?;
        """,
        (folder_id,),
    )
    bookmarks = [
        (
            row[5],
            Bookmark(
                row[0], folder_id, row[1], row[2], row[3], get_favicon(cur, row[4])
            ),
        )
        for row in bres.fetchall()
    ]

    if folders_first:
        bookmarks.sort(key=lambda e: e[0])
        entries.extend(bookmarks)
    else:
        entries.extend(bookmarks)
        entries.sort(key=lambda e: e[0])

    return [e[1] for e in entries]
