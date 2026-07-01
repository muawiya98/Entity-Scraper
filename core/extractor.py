"""Information extraction from a parsed web page.

Given a BeautifulSoup document and its raw text, pull out the structured
fields we care about: entity name, description, emails, phone numbers,
postal address, social profiles, and people (name + job title).

The extractors combine three strategies, from most to least reliable:
1. schema.org JSON-LD (and Open Graph meta tags)
2. ``mailto:`` / ``tel:`` links and microdata
3. Regex + keyword heuristics over visible text
"""
from __future__ import annotations 

import json 
import re 
from urllib .parse import urljoin ,urlparse 

import phonenumbers 
from bs4 import BeautifulSoup 

from core import llm 

import extruct 
from w3lib .html import remove_tags 

EMAIL_RE =re .compile (r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


_BAD_EMAIL_END =(".png",".jpg",".jpeg",".gif",".webp",".svg",".bmp",".css",".js")
_BAD_EMAIL_DOMAINS =("example.com","sentry.io","wix.com","domain.com","email.com")


ROLE_KEYWORDS_EN =[
"ceo","cfo","cto","coo","cmo","ciso","chief","chairman","chairperson",
"president","vice president","vp","managing director","general manager",
"director","manager","head of","founder","co-founder","cofounder",
"partner","owner","principal","dean","professor","consultant",
"supervisor","team lead","lead","officer","executive","coordinator",
"specialist","engineer","architect","advisor","secretary","treasurer",
"board member","deputy",
]
ROLE_KEYWORDS_AR =[
"الرئيس التنفيذي","المدير التنفيذي","المدير العام","نائب الرئيس",
"رئيس مجلس الإدارة","مدير عام","مدير","مديرة","رئيس","رئيسة","نائب",
"مؤسس","مؤسسة","شريك","مالك","عميد","أستاذ","دكتور","د.","مستشار",
"مشرف","مشرفة","مهندس","مهندسة","أخصائي","اخصائي","السكرتير",
"أمين","عضو مجلس الإدارة","نائبة",
]
ROLE_KEYWORDS =ROLE_KEYWORDS_EN +ROLE_KEYWORDS_AR 

SOCIAL_PATTERNS ={
"facebook":["facebook.com"],
"twitter":["twitter.com","x.com"],
"linkedin":["linkedin.com"],
"instagram":["instagram.com"],
"youtube":["youtube.com","youtu.be"],
"tiktok":["tiktok.com"],
"whatsapp":["wa.me","whatsapp.com","api.whatsapp.com"],
"telegram":["t.me","telegram.me"],
"snapchat":["snapchat.com"],
}

_ARABIC_RE =re .compile (r"[؀-ۿ]")


def _is_probably_name (text :str )->bool :
    """Heuristic: does this string look like a person's name?"""
    text =text .strip ()
    if not text or len (text )>60 :
        return False 
    if any (ch .isdigit ()for ch in text ):
        return False 
    if "@"in text or "http"in text .lower ():
        return False 
    words =text .split ()
    if not (1 <=len (words )<=5 ):
        return False 

    if _ARABIC_RE .search (text ):
        return True 

    cap =sum (1 for w in words if w [:1 ].isupper ())
    return cap >=max (1 ,len (words )-1 )


















def _json_ld_blocks (html :str ,base_url :str )->list :
    """Extract structured data (JSON-LD, Microdata, RDFa) using extruct."""
    blocks =[]
    try :
        metadata =extruct .extract (html ,base_url =base_url ,syntaxes =["json-ld","microdata","rdfa"])
        for syntax ,items in metadata .items ():
            if isinstance (items ,list ):
                blocks .extend (items )
            elif isinstance (items ,dict ):
                blocks .append (items )
    except Exception :
        pass 
    return blocks 

def _types (block :dict )->set [str ]:
    t =block .get ("@type","")
    if isinstance (t ,list ):
        return {str (x ).lower ()for x in t }
    return {str (t ).lower ()}





def extract_name (soup :BeautifulSoup ,url :str ,json_ld :list )->str :
    org_types ={"organization","corporation","localbusiness","educationalorganization",
    "collegeoruniversity","school","realestateagent","ngo"}
    for block in json_ld :
        if _types (block )&org_types and block .get ("name"):
            return str (block ["name"]).strip ()

    og =soup .find ("meta",property ="og:site_name")
    if og and og .get ("content"):
        return og ["content"].strip ()

    if soup .title and soup .title .string :
        title =re .split (r"[|\-–—:•]",soup .title .string )[0 ].strip ()
        if 2 <len (title )<80 :
            return title 

    h1 =soup .find ("h1")
    if h1 and h1 .get_text (strip =True ):
        return h1 .get_text (strip =True )[:80 ]

    return urlparse (url ).netloc .replace ("www.","")









def extract_description (soup :BeautifulSoup )->str :
    for sel in [("meta",{"name":"description"}),("meta",{"property":"og:description"})]:
        tag =soup .find (*sel [:1 ],attrs =sel [1 ])
        if tag and tag .get ("content"):
            return tag ["content"].strip ()[:500 ]


    about_tag =soup .select_one (".about-us, .description, #about, article")
    if about_tag :
        return remove_tags (str (about_tag )).strip ()[:500 ]

    return ""

def extract_emails (soup :BeautifulSoup ,text :str )->list [str ]:
    found :set [str ]=set ()
    for a in soup .select ('a[href^="mailto:"]'):
        addr =a ["href"][7 :].split ("?")[0 ].strip ()
        if addr :
            found .add (addr )
    for match in EMAIL_RE .findall (text ):
        found .add (match )

    cleaned =[]
    for email in found :
        e =email .strip ().strip (".").lower ()
        if e .endswith (_BAD_EMAIL_END ):
            continue 
        if any (bad in e for bad in _BAD_EMAIL_DOMAINS ):
            continue 
        if e not in cleaned :
            cleaned .append (e )
    return cleaned 


def extract_phones (soup :BeautifulSoup ,text :str ,region :str ="SA")->list [str ]:
    found :list [str ]=[]

    def _add (raw :str )->None :
        try :
            for match in phonenumbers .PhoneNumberMatcher (raw ,region ):
                num =phonenumbers .format_number (
                match .number ,phonenumbers .PhoneNumberFormat .INTERNATIONAL 
                )
                if num not in found :
                    found .append (num )
        except Exception :
            pass 

    for a in soup .select ('a[href^="tel:"]'):
        _add (a ["href"][4 :])
    _add (text )
    return found [:15 ]


def extract_address (soup :BeautifulSoup ,text :str ,json_ld :list )->tuple [str ,str ,str ]:
    """Return (address, city, country)."""
    for block in json_ld :
        addr =block .get ("address")
        if isinstance (addr ,dict ):
            parts =[
            addr .get ("streetAddress"),
            addr .get ("addressLocality"),
            addr .get ("addressRegion"),
            addr .get ("postalCode"),
            addr .get ("addressCountry"),
            ]
            full =", ".join (str (p )for p in parts if p )
            city =str (addr .get ("addressLocality")or "")
            country =str (addr .get ("addressCountry")or "")
            if isinstance (addr .get ("addressCountry"),dict ):
                country =str (addr ["addressCountry"].get ("name",""))
            if full :
                return full [:300 ],city ,country 
        elif isinstance (addr ,str )and addr .strip ():
            return addr .strip ()[:300 ],"",""


    node =soup .find (attrs ={"itemtype":re .compile ("PostalAddress",re .I )})
    if node :
        addr_text =node .get_text (" ",strip =True )
        if addr_text :
            return addr_text [:300 ],"",""

    return "","",""


def extract_social (soup :BeautifulSoup ,base_url :str )->dict [str ,str ]:
    social :dict [str ,str ]={}
    for a in soup .find_all ("a",href =True ):
        href =urljoin (base_url ,a ["href"])
        low =href .lower ()
        for name ,domains in SOCIAL_PATTERNS .items ():
            if name in social :
                continue 
            if any (d in low for d in domains ):

                if "sharer"in low or "intent"in low or low .rstrip ("/").endswith (tuple (domains )):
                    continue 
                social [name ]=href 
    return social 





def _people_from_json_ld (json_ld :list )->list [dict ]:
    people :list [dict ]=[]

    def _person (block :dict ,source ="json-ld")->None :
        if "person"not in _types (block ):
            return 
        name =block .get ("name")
        if not name :
            return 
        people .append (
        {
        "name":str (name ).strip (),
        "position":str (block .get ("jobTitle")or "").strip (),
        "email":str (block .get ("email")or "").strip ().replace ("mailto:",""),
        "phone":str (block .get ("telephone")or "").strip (),
        "profile_url":str (block .get ("url")or "").strip (),
        "source":source ,
        }
        )

    for block in json_ld :
        _person (block )
        for key in ("employee","employees","founder","member","members","founders"):
            val =block .get (key )
            if isinstance (val ,list ):
                for v in val :
                    if isinstance (v ,dict ):
                        _person (v ,source =f"json-ld:{key }")
            elif isinstance (val ,dict ):
                _person (val ,source =f"json-ld:{key }")
    return people 


def _line_has_role (line :str )->str |None :
    low =line .lower ()
    for kw in ROLE_KEYWORDS :
        if kw in low or kw in line :
            return kw 
    return None 


def _people_from_cards (soup :BeautifulSoup )->list [dict ]:
    """Look for 'team card' structures: a heading (name) near a role line."""
    people :list [dict ]=[]
    seen :set [str ]=set ()


    containers =soup .select (
    "div, li, article, section, td, figure"
    )
    for c in containers :

        text =c .get_text ("\n",strip =True )
        if not text or len (text )>400 :
            continue 
        heading =c .find (["h1","h2","h3","h4","h5","strong","b"])
        if not heading :
            continue 
        name =heading .get_text (strip =True )
        if not _is_probably_name (name )or name .lower ()in seen :
            continue 


        position =""
        for line in text .split ("\n"):
            line =line .strip ()
            if line and line !=name and _line_has_role (line )and len (line )<80 :
                position =line 
                break 
        if not position :
            continue 


        email =""
        mail =c .select_one ('a[href^="mailto:"]')
        if mail :
            email =mail ["href"][7 :].split ("?")[0 ]
        profile =""
        link =c .find ("a",href =True )
        if link and "mailto:"not in link ["href"]and "tel:"not in link ["href"]:
            profile =link ["href"]

        seen .add (name .lower ())
        people .append (
        {
        "name":name ,
        "position":position ,
        "email":email ,
        "phone":"",
        "profile_url":profile ,
        "source":"team-card",
        }
        )
    return people 


def _people_from_text (text :str )->list [dict ]:
    """Catch 'Name - Title' / 'Title: Name' patterns in flowing text."""
    people :list [dict ]=[]
    seen :set [str ]=set ()
    for raw in text .split ("\n"):
        line =raw .strip ()
        if not line or len (line )>90 :
            continue 
        role =_line_has_role (line )
        if not role :
            continue 

        for sep in (" - "," – "," — ",", "," | ",": "," / "):
            if sep in line :
                left ,right =line .split (sep ,1 )
                left ,right =left .strip (),right .strip ()

                if _line_has_role (left )and _is_probably_name (right ):
                    name ,position =right ,left 
                elif _line_has_role (right )and _is_probably_name (left ):
                    name ,position =left ,right 
                else :
                    continue 
                if name .lower ()in seen :
                    break 
                seen .add (name .lower ())
                people .append (
                {
                "name":name ,
                "position":position ,
                "email":"",
                "phone":"",
                "profile_url":"",
                "source":"text",
                }
                )
                break 
    return people 


def extract_people (soup :BeautifulSoup ,text :str ,json_ld :list )->list [dict ]:
    people =_people_from_json_ld (json_ld )
    people +=_people_from_cards (soup )
    people +=_people_from_text (text )


    merged :dict [str ,dict ]={}
    for p in people :
        if not p .get ("name"):
            continue 
        key =p ["name"].lower ().strip ()
        if key not in merged :
            merged [key ]=p 
        else :
            existing =merged [key ]
            for field in ("position","email","phone","profile_url"):
                if not existing .get (field )and p .get (field ):
                    existing [field ]=p [field ]
    return list (merged .values ())


def _merge_llm_extract (result :dict ,llm_data :dict )->dict :
    if not llm_data :
        return result 

    if llm_data .get ("name")and not result .get ("name"):
        result ["name"]=str (llm_data ["name"]).strip ()
    if llm_data .get ("description")and not result .get ("description"):
        result ["description"]=str (llm_data ["description"]).strip ()[:500 ]

    address =llm_data .get ("address")
    city =str (llm_data .get ("city")or "")
    country =str (llm_data .get ("country")or "")
    current_addr ,current_city ,current_country =result .get ("address",("","",""))
    if address and not current_addr :
        result ["address"]=(str (address ).strip ()[:300 ],city ,country )
    elif current_addr and (city or country )and (not current_city or not current_country ):
        result ["address"]=(
        current_addr ,
        current_city or city ,
        current_country or country ,
        )

    for key in ("emails","phones"):
        values =llm_data .get (key )
        if isinstance (values ,list ):
            for value in values :
                value =str (value ).strip ()
                if value and value not in result [key ]:
                    result [key ].append (value )

    social =llm_data .get ("social")
    if isinstance (social ,dict ):
        for key ,value in social .items ():
            if value and key not in result ["social"]:
                result ["social"][str (key )]=str (value )

    people =llm_data .get ("people")
    if isinstance (people ,list ):
        seen ={p .get ("name","").lower ().strip ()for p in result ["people"]}
        for person in people :
            if not isinstance (person ,dict ):
                continue 
            name =str (person .get ("name")or "").strip ()
            if not name or name .lower ()in seen :
                continue 
            seen .add (name .lower ())
            result ["people"].append (
            {
            "name":name ,
            "position":str (person .get ("position")or "").strip (),
            "email":str (person .get ("email")or "").strip (),
            "phone":str (person .get ("phone")or "").strip (),
            "profile_url":str (person .get ("profile_url")or "").strip (),
            "source":"llm-text",
            }
            )

    result .setdefault ("meta",{})["llm_page_extract"]=True 
    return result 


def parse_page (html :str ,url :str ,region :str ="SA")->dict :
    """Run every extractor on a single page and return the partial record."""
    soup =BeautifulSoup (html ,"lxml")

    for tag in soup (["script","style","noscript","svg"]):
        tag .decompose ()
    text =soup .get_text ("\n",strip =True )

    json_ld =_json_ld_blocks (html ,url )

    result ={
    "name":extract_name (soup ,url ,json_ld ),
    "description":extract_description (soup ),
    "emails":extract_emails (soup ,text ),
    "phones":extract_phones (soup ,text ,region ),
    "address":extract_address (soup ,text ,json_ld ),
    "social":extract_social (soup ,url ),
    "people":extract_people (soup ,text ,json_ld ),
    "meta":{},
    }

    if llm .enabled ():
        result =_merge_llm_extract (
        result ,
        llm .extract_from_page_text (text ,url ,existing =result ),
        )

    return result 
