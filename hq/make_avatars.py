"""Generate 10 original vector profile pictures for AshenToons HQ.

These are locally generated avatars for FICTIONAL studio roles,
not synthetic manga panels or representations of real employees.
"""
from pathlib import Path
from html import escape

OUT=Path(r"D:\AshenToons\control-room\avatars")
OUT.mkdir(parents=True,exist_ok=True)
PEOPLE=[
("ceo","#9476f7","#322153","#e4b697","#191527","wave","violet","star",0),
("operator","#3dbcc5","#103e4b","#d19b7f","#182937","swept","navy","headset",1),
("management","#d49aed","#422455","#eed0ba","#51334e","bun","purple","glasses",2),
("story","#f2b56f","#643b1c","#d9a47e","#403328","messy","orange","pen",3),
("source","#87b8fa","#263f6a","#deb68b","#253047","fringe","blue","glasses",4),
("audio","#6dd7ae","#1b5146","#eab49b","#253b37","long","green","headphones",5),
("editing","#fb927f","#65332d","#c58c73","#282a3b","spike","red","camera",6),
("qa","#f4c86b","#5e4b1d","#e3b496","#1b2533","bob","gold","glasses",7),
("thumbnail","#f081b6","#6b254e","#deb091","#482c50","side","pink","star",8),
("publishing","#b7bcda","#37435c","#cf9d83","#293248","swept","silver","tie",9),
]

def accessory(kind, accent):
    if kind=="star":return f'<path d="M72 17l2.8 5.5 6.1 1-4.4 4.5 1 6.1-5.5-3-5.6 3 1.1-6.1-4.4-4.5 6-1z" fill="{accent}" stroke="#fff" stroke-width="1.4"/>'
    if kind=="glasses":return '<g stroke="#253044" stroke-width="2.3" fill="none"><rect x="33" y="51" width="19" height="13" rx="5"/><rect x="60" y="51" width="19" height="13" rx="5"/><path d="M52 55q4-3 8 0M32 55l-8-2M79 55l8-2"/></g>'
    if kind=="headphones":return f'<path d="M29 59v-10a27 27 0 0 1 54 0v10" stroke="{accent}" stroke-width="8" fill="none"/><rect x="23" y="51" width="11" height="20" rx="5" fill="#182134"/><rect x="78" y="51" width="11" height="20" rx="5" fill="#182134"/>'
    if kind=="headset":return f'<path d="M27 57v-9a28 28 0 0 1 56 0v8" fill="none" stroke="{accent}" stroke-width="5"/><path d="M82 63v9q-7 10-20 10" stroke="{accent}" fill="none" stroke-width="3"/><circle cx="60" cy="82" r="4" fill="{accent}"/>'
    if kind=="pen":return f'<path d="M82 89l13-17 5 4-13 17-9 4z" fill="#eee" stroke="{accent}" stroke-width="1.2"/>'
    if kind=="camera":return '<rect x="78" y="82" width="24" height="16" rx="4" fill="#1c2a35" stroke="#aebbd1" stroke-width="2"/><circle cx="90" cy="90" r="5" fill="#5b7089" stroke="#c8e3f5" stroke-width="2"/>'
    if kind=="tie":return f'<path d="M55 85l-5 7 6 16 6-16-5-7z" fill="{accent}"/>'
    return ""

def hair_shape(style, color):
    common = {
    "wave":'M29 54Q21 29 40 23Q54 9 76 21Q94 35 82 60L76 49Q71 37 60 38Q44 29 34 49z',
    "swept":'M29 53Q24 24 49 21Q70 12 83 34L81 54Q74 43 69 38Q47 47 33 45z',
    "bun":'M27 57Q19 29 37 26Q51 10 70 23Q87 30 84 57L77 49Q62 33 35 46z',
    "messy":'M27 52L27 29L40 34L38 18L50 24L59 15L65 27L78 21L75 34L87 30L83 56L75 49Q58 36 33 48z',
    "fringe":'M27 53Q20 30 43 20Q69 11 82 37L80 54L68 43L62 48L51 42L44 48L34 46z',
    "long":'M26 91Q16 61 26 37Q29 18 54 19Q83 16 88 47Q94 79 87 98L74 96Q83 74 74 53L37 43Q26 73 39 94z',
    "spike":'M27 53L23 23L39 30L44 14L56 23L70 14L77 29L91 23L83 54Q68 40 32 49z',
    "bob":'M25 77Q20 52 27 36Q35 12 60 18Q83 18 88 44Q91 66 81 79L76 54Q63 36 34 49z',
    "side":'M25 55Q23 26 42 21Q66 10 84 34L80 62L73 46Q55 46 46 37Q40 48 33 52z',
    }
    return f'<path d="{common[style]}" fill="{color}" stroke="#151622" stroke-width="1.5" stroke-linejoin="round"/>'

for key,accent,dark,skin,hair,style,clothes,extra,i in PEOPLE:
    skinShadow = "#a77960" if i in (1,4,6,9) else "#c0927e"
    hairBack = f'<ellipse cx="56" cy="53" rx="32" ry="37" fill="{hair}"/>' if style in ("long","bob") else ''
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 112 112" role="img" aria-label="{escape(key)} avatar">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{dark}"/><stop offset="1" stop-color="#0a1323"/></linearGradient>
<linearGradient id="jacket" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{accent}"/><stop offset="1" stop-color="{dark}"/></linearGradient></defs>
<rect width="112" height="112" rx="30" fill="url(#bg)"/>
<circle cx="83" cy="27" r="48" fill="{accent}" opacity=".10"/>
<circle cx="24" cy="15" r="17" fill="none" stroke="{accent}" opacity=".17"/>
<path d="M0 89Q56 107 112 72v40H0z" fill="{accent}" opacity=".16"/>
<ellipse cx="56" cy="114" rx="52" ry="33" fill="#10192c"/>
<path d="M15 112Q15 91 34 87L44 83L48 75H65L69 83L80 87Q98 92 98 112" fill="url(#jacket)" stroke="#101b2b" stroke-width="2"/>
<path d="M44 84l13 14 12-14-6-7H51z" fill="#ebebed" opacity=".89"/>
<path d="M48 76q0 6-5 10l13 12 13-12q-5-4-5-10" fill="{skin}"/>
{hairBack}
<ellipse cx="56" cy="54" rx="28" ry="31" fill="{skin}" stroke="{skinShadow}" stroke-width="1.4"/>
<path d="M31 56q1 23 23 29q-14-2-21-13" fill="{skinShadow}" opacity=".22"/>
{hair_shape(style,hair)}
<path d="M38 52q7-4 14 0M62 52q8-4 14 0" fill="none" stroke="{hair}" stroke-width="2.4" stroke-linecap="round"/>
<ellipse cx="45" cy="59" rx="2.6" ry="3.2" fill="#172233"/>
<ellipse cx="68" cy="59" rx="2.6" ry="3.2" fill="#172233"/>
<path d="M56 61l-2 9 4 1" fill="none" stroke="{skinShadow}" stroke-width="1.4" stroke-linecap="round"/>
<path d="M47 76q9 7 18 0" fill="none" stroke="#774944" stroke-width="2" stroke-linecap="round"/>
<circle cx="20" cy="22" r="4" fill="{accent}" opacity=".42"/>
{accessory(extra,accent)}
<rect x="1.5" y="1.5" width="109" height="109" rx="29" fill="none" stroke="{accent}" stroke-width="2" opacity=".48"/>
</svg>'''
    path=OUT/(key+".svg")
    if path.exists(): raise RuntimeError("Avatar unexpectedly exists "+str(path))
    path.write_text(svg,encoding="utf8")
    print("PFP",key,path,len(svg),flush=True)
print("AVATARS_CREATED",len(PEOPLE),flush=True)
