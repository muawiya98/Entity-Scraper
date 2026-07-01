"""SQLite persistence layer.

The database is intentionally simple and dependency-free (standard-library
``sqlite3``).  Each call opens its own short-lived connection, which keeps the
layer safe to use from the Flask request thread *and* the background scraping
thread simultaneously.
"""
from __future__ import annotations 

import json 
import sqlite3 
from contextlib import contextmanager 
from datetime import datetime ,timezone 
from typing import Any ,Iterable 

from config import config 

SCHEMA ="""
CREATE TABLE IF NOT EXISTS searches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query         TEXT NOT NULL,
    location      TEXT,
    entity_type   TEXT,
    max_results   INTEGER,
    status        TEXT DEFAULT 'pending',
    progress      INTEGER DEFAULT 0,
    message       TEXT,
    results_count INTEGER DEFAULT 0,
    created_at    TEXT,
    completed_at  TEXT
);

CREATE TABLE IF NOT EXISTS entities (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id    INTEGER,
    name         TEXT,
    website      TEXT,
    domain       TEXT,
    description  TEXT,
    address      TEXT,
    city         TEXT,
    country      TEXT,
    phones       TEXT,   -- JSON array
    emails       TEXT,   -- JSON array
    social       TEXT,   -- JSON object
    meta         TEXT,   -- JSON object (extra fields)
    created_at   TEXT,
    FOREIGN KEY (search_id) REFERENCES searches (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS people (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id   INTEGER,
    name        TEXT,
    position    TEXT,
    email       TEXT,
    phone       TEXT,
    profile_url TEXT,
    source      TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id   INTEGER,
    url         TEXT,
    page_type   TEXT,
    status_code INTEGER,
    fetched_at  TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_search ON entities (search_id);
CREATE INDEX IF NOT EXISTS idx_people_entity ON people (entity_id);
CREATE INDEX IF NOT EXISTS idx_pages_entity ON pages (entity_id);
"""


def _now ()->str :
    return datetime .now (timezone .utc ).isoformat (timespec ="seconds")


@contextmanager 
def get_conn ():
    conn =sqlite3 .connect (config .DB_PATH ,timeout =30 )
    conn .row_factory =sqlite3 .Row 
    conn .execute ("PRAGMA foreign_keys = ON")
    try :
        yield conn 
        conn .commit ()
    finally :
        conn .close ()


def init_db ()->None :
    with get_conn ()as conn :
        conn .executescript (SCHEMA )





def create_search (query :str ,location :str ,entity_type :str ,max_results :int )->int :
    with get_conn ()as conn :
        cur =conn .execute (
        """INSERT INTO searches (query, location, entity_type, max_results,
                                     status, progress, message, created_at)
               VALUES (?, ?, ?, ?, 'pending', 0, '', ?)""",
        (query ,location ,entity_type ,max_results ,_now ()),
        )
        return int (cur .lastrowid )


def update_search (search_id :int ,**fields :Any )->None :
    if not fields :
        return 
    cols =", ".join (f"{k } = ?"for k in fields )
    values =list (fields .values ())+[search_id ]
    with get_conn ()as conn :
        conn .execute (f"UPDATE searches SET {cols } WHERE id = ?",values )


def get_search (search_id :int )->dict |None :
    with get_conn ()as conn :
        row =conn .execute ("SELECT * FROM searches WHERE id = ?",(search_id ,)).fetchone ()
        return dict (row )if row else None 


def list_searches (limit :int =100 )->list [dict ]:
    with get_conn ()as conn :
        rows =conn .execute (
        "SELECT * FROM searches ORDER BY id DESC LIMIT ?",(limit ,)
        ).fetchall ()
        return [dict (r )for r in rows ]


def delete_search (search_id :int )->None :
    with get_conn ()as conn :
        conn .execute ("DELETE FROM searches WHERE id = ?",(search_id ,))





def insert_entity (search_id :int ,data :dict )->int :
    with get_conn ()as conn :
        cur =conn .execute (
        """INSERT INTO entities
               (search_id, name, website, domain, description, address, city,
                country, phones, emails, social, meta, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
        search_id ,
        data .get ("name"),
        data .get ("website"),
        data .get ("domain"),
        data .get ("description"),
        data .get ("address"),
        data .get ("city"),
        data .get ("country"),
        json .dumps (data .get ("phones",[]),ensure_ascii =False ),
        json .dumps (data .get ("emails",[]),ensure_ascii =False ),
        json .dumps (data .get ("social",{}),ensure_ascii =False ),
        json .dumps (data .get ("meta",{}),ensure_ascii =False ),
        _now (),
        ),
        )
        entity_id =int (cur .lastrowid )

        for person in data .get ("people",[]):
            conn .execute (
            """INSERT INTO people
                   (entity_id, name, position, email, phone, profile_url, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
            entity_id ,
            person .get ("name"),
            person .get ("position"),
            person .get ("email"),
            person .get ("phone"),
            person .get ("profile_url"),
            person .get ("source"),
            ),
            )

        for page in data .get ("pages",[]):
            conn .execute (
            """INSERT INTO pages (entity_id, url, page_type, status_code, fetched_at)
                   VALUES (?, ?, ?, ?, ?)""",
            (
            entity_id ,
            page .get ("url"),
            page .get ("page_type"),
            page .get ("status_code"),
            _now (),
            ),
            )
        return entity_id 


def _row_to_entity (conn :sqlite3 .Connection ,row :sqlite3 .Row )->dict :
    entity =dict (row )
    for key in ("phones","emails","social","meta"):
        try :
            entity [key ]=json .loads (entity [key ])if entity [key ]else ([]if key in ("phones","emails")else {})
        except (json .JSONDecodeError ,TypeError ):
            entity [key ]=[]if key in ("phones","emails")else {}
    people =conn .execute (
    "SELECT name, position, email, phone, profile_url, source FROM people WHERE entity_id = ?",
    (entity ["id"],),
    ).fetchall ()
    entity ["people"]=[dict (p )for p in people ]
    pages =conn .execute (
    "SELECT url, page_type, status_code, fetched_at FROM pages WHERE entity_id = ?",
    (entity ["id"],),
    ).fetchall ()
    entity ["pages"]=[dict (p )for p in pages ]
    return entity 


def get_entities_for_search (search_id :int )->list [dict ]:
    with get_conn ()as conn :
        rows =conn .execute (
        "SELECT * FROM entities WHERE search_id = ? ORDER BY id",(search_id ,)
        ).fetchall ()
        return [_row_to_entity (conn ,r )for r in rows ]


def get_entity (entity_id :int )->dict |None :
    with get_conn ()as conn :
        row =conn .execute ("SELECT * FROM entities WHERE id = ?",(entity_id ,)).fetchone ()
        return _row_to_entity (conn ,row )if row else None 


def existing_domains (search_id :int )->set [str ]:
    with get_conn ()as conn :
        rows =conn .execute (
        "SELECT domain FROM entities WHERE search_id = ?",(search_id ,)
        ).fetchall ()
        return {r ["domain"]for r in rows if r ["domain"]}


def stats ()->dict :
    with get_conn ()as conn :
        searches =conn .execute ("SELECT COUNT(*) c FROM searches").fetchone ()["c"]
        entities =conn .execute ("SELECT COUNT(*) c FROM entities").fetchone ()["c"]
        people =conn .execute ("SELECT COUNT(*) c FROM people").fetchone ()["c"]
    return {"searches":searches ,"entities":entities ,"people":people }
