CREATE TABLE IF NOT EXISTS folders(
    folder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER,
    title TEXT NOT NULL,

    FOREIGN KEY(parent_id) REFERENCES folders(folder_id)
);

-- These are in separate tables, so I can change it more easily later.
-- See here for future methods:
-- https://begriffs.com/posts/2018-03-20-user-defined-order.html
-- https://news.ycombinator.com/item?id=16635440
-- https://news.ycombinator.com/item?id=25797674
CREATE TABLE IF NOT EXISTS folders_order(
    folder_id INTEGER PRIMARY KEY,
    sort_key INTEGER,

    FOREIGN KEY(folder_id) REFERENCES folders(folder_id)
);

CREATE TABLE IF NOT EXISTS bookmarks(
    bookmark_id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    comment TEXT,

    FOREIGN KEY(folder_id) REFERENCES folders(folder_id)
);

CREATE TABLE IF NOT EXISTS bookmarks_order(
    bookmark_id INTEGER PRIMARY KEY,
    sort_key INTEGER,

    FOREIGN KEY(bookmark_id) REFERENCES bookmarks(bookmark_id)
);

-- Make sure root folder exists
INSERT OR IGNORE INTO folders(folder_id, parent_id, title) VALUES(0, NULL, "");
