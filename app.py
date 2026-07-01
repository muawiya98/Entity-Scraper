"""Entity Scraper - Flask web application.

Run with:  python app.py
Then open  http://127.0.0.1:5000  in your browser.
"""
from __future__ import annotations 

import logging 
import threading 

from flask import Flask ,abort ,jsonify ,render_template ,request ,send_file 

from config import config 
from core import database ,exporter ,llm ,pipeline 

logging .basicConfig (
level =logging .INFO ,
format ="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log =logging .getLogger ("entity-scraper")

app =Flask (__name__ )
app .config ["SECRET_KEY"]=config .SECRET_KEY 
app .json .ensure_ascii =False 

database .init_db ()





@app .route ("/")
def index ():
    return render_template (
    "index.html",
    backends =config .available_backends (),
    llm =config .available_llm (),
    )


@app .route ("/searches")
def searches_page ():
    return render_template ("searches.html")


@app .route ("/search/<int:search_id>")
def search_detail_page (search_id :int ):
    if not database .get_search (search_id ):
        abort (404 )
    return render_template ("results.html",search_id =search_id )





@app .post ("/api/search")
def api_start_search ():
    data =request .get_json (force =True ,silent =True )or {}
    query =(data .get ("query")or "").strip ()
    if not query :
        return jsonify ({"error":"query is required"}),400 

    location =(data .get ("location")or "").strip ()
    entity_type =(data .get ("entity_type")or "").strip ()
    try :
        max_results =max (1 ,min (30 ,int (data .get ("max_results",10 ))))
    except (TypeError ,ValueError ):
        max_results =10 

    search_id =database .create_search (query ,location ,entity_type ,max_results )
    thread =threading .Thread (target =pipeline .run_pipeline ,args =(search_id ,),daemon =True )
    thread .start ()
    return jsonify ({"search_id":search_id }),202 


@app .get ("/api/search/<int:search_id>/status")
def api_search_status (search_id :int ):
    search =database .get_search (search_id )
    if not search :
        return jsonify ({"error":"not found"}),404 
    return jsonify (
    {
    "id":search ["id"],
    "status":search ["status"],
    "progress":search ["progress"],
    "message":search ["message"],
    "results_count":search ["results_count"],
    }
    )


@app .get ("/api/search/<int:search_id>/results")
def api_search_results (search_id :int ):
    search =database .get_search (search_id )
    if not search :
        return jsonify ({"error":"not found"}),404 
    return jsonify ({"search":search ,"entities":database .get_entities_for_search (search_id )})


@app .get ("/api/searches")
def api_list_searches ():
    return jsonify ({"searches":database .list_searches ()})


@app .delete ("/api/search/<int:search_id>")
def api_delete_search (search_id :int ):
    database .delete_search (search_id )
    return jsonify ({"ok":True })


@app .get ("/api/entity/<int:entity_id>")
def api_entity (entity_id :int ):
    entity =database .get_entity (entity_id )
    if not entity :
        return jsonify ({"error":"not found"}),404 
    return jsonify (entity )


@app .get ("/api/search/<int:search_id>/export")
def api_export (search_id :int ):
    if not database .get_search (search_id ):
        return jsonify ({"error":"not found"}),404 
    path =exporter .export_search (search_id )
    return send_file (path ,as_attachment =True ,mimetype ="application/json")

@app .get ("/api/search/<int:search_id>/export/excel")
def api_export_excel (search_id :int ):
    if not database .get_search (search_id ):
        return jsonify ({"error":"not found"}),404 
    try :
        path =exporter .export_excel (search_id )
        return send_file (
        path ,
        as_attachment =True ,
        mimetype ="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except ImportError :
        return jsonify ({"error":"openpyxl is not installed. Please run: pip install openpyxl"}),500 

@app .get ("/api/stats")
def api_stats ():
    data =database .stats ()
    data ["llm"]=llm .status ()
    return jsonify (data )


if __name__ =="__main__":
    print ("\n  Entity Scraper running at  http://127.0.0.1:5000\n")
    app .run (host ="127.0.0.1",port =5000 ,debug =False )
