#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construit une version « complète » de l’application annonces-bodacc-france.html,
avec les annonces de tous les statuts embarquées (utilisables hors ligne).

Usage (dans le dossier qui contient annonces-bodacc-france.html) :
    python construire_base_bodacc.py
Options utiles :
    --depuis 2025-01-01        début de la période (pas avant 2025-01-01)
    --jusqu 2026-11-08         fin de la période (par défaut : aujourd’hui)
    --departements 33,24,47    limite le détail annonce par annonce à ces départements
                               (les volumes par statut restent nationaux)
    --tout                     embarque aussi le détail des modifications et des dépôts des comptes
                               (plusieurs millions d’annonces : fichier très lourd)
    --sortie mon-fichier.html  nom du fichier produit

Le script n’utilise que la bibliothèque standard de Python (3.8+). Les téléchargements
sont mis en cache dans le dossier .cache_bodacc : une seconde exécution ne télécharge
que les semaines manquantes ou récentes. Les noms des personnes et des entreprises ne
sont pas conservés : seuls la date, la commune, le SIREN, l’activité déclarée et la
nature de l’annonce sont gardés.
"""
import argparse, base64, datetime as dt, gzip, json, os, re, sys, time, unicodedata
import urllib.parse, urllib.request, urllib.error

HOTES = [os.environ['BODACC_API']] if os.environ.get('BODACC_API') else [
    'https://www.bodacc.fr/api/explore/v2.1/catalog/datasets/annonces-commerciales',
    'https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales',
]
API = HOTES[0]
FAMS = ['immatriculation', 'creation', 'modification', 'vente', 'radiation', 'collective',
        'conciliation', 'retablissement_professionnel', 'dpc', 'divers', 'autre']
DETAIL_DEFAUT = ['immatriculation', 'creation', 'radiation', 'collective', 'conciliation', 'retablissement_professionnel', 'divers']
J0 = dt.date(2025, 1, 1)

CHAMPS = {
    'immatriculation': 'acte,listeetablissements,listepersonnes',
    'creation': 'acte,listeetablissements,listepersonnes',
    'modification': 'modificationsgenerales,listeetablissements,listepersonnes',
    'radiation': 'radiationaurcs,acte,listeetablissements,listepersonnes',
    'collective': 'jugement,acte,listeetablissements,listepersonnes',
    'conciliation': 'jugement,acte,listeetablissements,listepersonnes',
    'retablissement_professionnel': 'jugement,acte,listeetablissements,listepersonnes',
    'divers': 'jugement,acte,listeetablissements,listepersonnes',
    'dpc': 'depot',
}

# ---------- Normalisation identique à l’application ----------
def norm(s):
    s = unicodedata.normalize('NFD', str(s or '').lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\bst\b', 'saint', s)
    s = re.sub(r'\bste\b', 'sainte', s)
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()

def clean_ville(v):
    v = re.split(r',|;| / ', str(v or ''))[0]
    v = re.sub(r'(?i)\s+cedex.*$', '', v)
    v = re.sub(r'\s+\d+$', '', v)
    return v.strip()

def parse(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v

def get_key(o, keys, depth=0):
    if not isinstance(o, (dict, list)) or depth > 5:
        return ''
    if isinstance(o, list):
        return get_key(o[0], keys, depth + 1) if o else ''
    for k in keys:
        v = o.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for v in o.values():
        r = get_key(v, keys, depth + 1)
        if r:
            return r
    return ''

PERSO = re.compile(r'^(nom|prenom|prenoms|denomination|nomusage|nomcommercial|personne|personnes|adresse|numerovoie|typevoie|nomvoie|codepostal|ville|complgeographique|pays|administration)$', re.I)
def all_text(v):
    v = parse(v)
    if not v:
        return ''
    if isinstance(v, str):
        return v
    out = []
    def walk(o, d):
        if d > 6 or o is None:
            return
        if isinstance(o, str):
            out.append(o); return
        if isinstance(o, list):
            for x in o: walk(x, d + 1)
            return
        if isinstance(o, dict):
            for k, x in o.items():
                if PERSO.match(k):
                    continue
                walk(x, d + 1)
    walk(v, 0)
    return ' '.join(out)

RAD_MOTIFS = [
    ('Clôture de liquidation', r'cloture.*liquidation|liquidation amiable|cloture des operations'),
    ('Fusion ou transmission universelle', r'fusion|transmission universelle|absorption'),
    ('Transfert hors ressort', r'transfert'),
    ('Cessation d’activité', r'cessation'),
    ('Décès', r'deces'),
    ('Radiation d’office', r'd office'),
]
MODIF_RULES = [
    r'administration|dirigeant|gerant|president|directeur general|commissaire aux comptes|associe',
    r'transfert', r'capital', r'denomination|nom commercial|enseigne|sigle', r'activite|objet social',
    r'forme juridique|transformation', r'dissolution', r'sommeil|cessation temporaire|reprise d activite',
]

def capital_of(lp):
    # Seul le montant du capital social est lu ; les noms des personnes sont ignorés.
    v = parse(lp)
    def find(o, d):
        if d > 5 or o is None:
            return None
        if isinstance(o, list):
            return find(o[0], d + 1) if o else None
        if not isinstance(o, dict):
            return None
        if o.get('montantCapital') is not None:
            return o['montantCapital']
        if isinstance(o.get('capital'), (int, float, str)):
            return o['capital']
        for x in o.values():
            r = find(x, d + 1)
            if r is not None:
                return r
        return None
    x = find(v, 0)
    if x is None:
        return 0
    s_ = re.sub(r'[^0-9.,\s]', '', str(x)).strip().replace(' ', '').replace('\u00a0', '').replace('\u202f', '')
    if not s_:
        return 0
    cut = max(s_.rfind('.'), s_.rfind(','))
    ent, dec = s_, ''
    if cut != -1 and len(s_) - cut - 1 <= 2 and s_[cut + 1:].isdigit():
        ent, dec = s_[:cut], s_[cut + 1:]
    ent = re.sub(r'[.,]', '', ent)
    if not ent.isdigit():
        return 0
    n = float(ent + '.' + (dec or '0'))
    return int(round(n)) if 0 < n < 1e11 else 0

def siren_of(reg):
    if isinstance(reg, list):
        x = next((s for s in reg if len(re.sub(r'\D', '', str(s))) == 9), reg[0] if reg else '')
    else:
        x = reg
    return re.sub(r'\D', '', str(x or ''))[:9]

# ---------- HTTP ----------
def get_json(path, params, tries=5):
    global API
    q = '?' + urllib.parse.urlencode(params)
    for i in range(tries):
        url = API + path + q
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'construire-base-bodacc/1.0', 'Accept-Encoding': 'gzip'})
            with urllib.request.urlopen(req, timeout=600) as r:
                raw = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 400:
                raise RuntimeError('Requête refusée par le BODACC : ' + e.read().decode('utf-8', 'replace')[:300])
            err = e
        except Exception as e:
            err = e
        if len(HOTES) > 1:                       # on essaie l’autre adresse du BODACC
            API = HOTES[(HOTES.index(API) + 1) % len(HOTES)]
        wait = 5 * (i + 1)
        print(f'    nouvelle tentative dans {wait} s ({err})', flush=True)
        time.sleep(wait)
    raise RuntimeError(f'Le BODACC ne répond pas : {url}')

def rows_of(j):
    return j if isinstance(j, list) else (j.get('results') or [])

# ---------- Programme ----------
def main():
    ap = argparse.ArgumentParser(description='Embarque toutes les annonces BODACC dans l’application.')
    ap.add_argument('--html', default='annonces-bodacc-france.html')
    ap.add_argument('--sortie', default=None)
    ap.add_argument('--depuis', default='2025-01-01')
    ap.add_argument('--jusqu', default=dt.date.today().isoformat())
    ap.add_argument('--departements', default='')
    ap.add_argument('--tout', action='store_true')
    a = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    src = a.html if os.path.isabs(a.html) else os.path.join(os.getcwd(), a.html)
    if not os.path.exists(src):
        src = os.path.join(here, a.html)
    if not os.path.exists(src):
        sys.exit(f'Fichier introuvable : {a.html}. Placez ce script à côté de annonces-bodacc-france.html.')
    out_path = a.sortie or re.sub(r'\.html$', '', src) + '-complet.html'
    cache = os.path.join(os.path.dirname(src), '.cache_bodacc')
    os.makedirs(cache, exist_ok=True)

    d0 = max(dt.date.fromisoformat(a.depuis), J0)
    d1 = min(dt.date.fromisoformat(a.jusqu), dt.date.today())
    if d1 < d0:
        sys.exit('Période vide.')
    detail = DETAIL_DEFAUT + (['modification', 'dpc'] if a.tout else [])
    deps_filtre = {x.strip().upper() for x in a.departements.split(',') if x.strip()}

    html = open(src, encoding='utf-8').read()
    m = re.search(r'(<script id="payload" type="application/octet-stream">)(.*?)(</script>)', html, re.S)
    if not m:
        sys.exit('Ce fichier ne contient pas les données attendues.')
    D = json.loads(gzip.decompress(base64.b64decode(m.group(2).strip())).decode('utf-8'))

    # Référentiels de l’application
    deps = D['deps']
    dep_idx = {d[0]: i for i, d in enumerate(deps)}
    com = D['communes']
    look = {}
    for i, (n, d) in enumerate(zip(com['nom'], com['d'])):
        look.setdefault((d, norm(n)), i)
    for d, n, i in D['alias']:
        look.setdefault((d, norm(n)), i)
    def geocode(d, v):
        n = norm(clean_ville(v))
        return look.get((d, n), -1) if n else -1
    def dep_of(code):
        code = str(code or '').strip().upper()
        if code in dep_idx:
            return dep_idx[code]
        if code.isdigit() and len(code) == 1:
            return dep_idx.get('0' + code)
        return None

    recent = dt.date.today() - dt.timedelta(days=10)

    # 1) Volumes par département, commune, statut et mois (tous statuts)
    print('1/2  Volumes par statut, département et commune…', flush=True)
    agg = {'m': [], 'd': [], 'c': [], 'f': [], 'n': []}
    mois = []
    y, mo = d0.year, d0.month
    while dt.date(y, mo, 1) <= d1:
        mois.append((y, mo)); mo += 1
        if mo > 12: mo = 1; y += 1
    for (y, mo) in mois:
        a_ = max(dt.date(y, mo, 1), d0)
        fin = (dt.date(y + (mo == 12), mo % 12 + 1, 1) - dt.timedelta(days=1))
        b_ = min(fin, d1)
        cf = os.path.join(cache, f'agg_{a_}_{b_}.json.gz')
        if os.path.exists(cf) and b_ < recent:
            res = json.loads(gzip.decompress(open(cf, 'rb').read()))
        else:
            print(f'  {y}-{mo:02d}', flush=True)
            res = rows_of(get_json('/exports/json', {
                'select': 'numerodepartement, ville, familleavis, count(*) as n',
                'where': f"dateparution>=date'{a_}' and dateparution<=date'{b_}'",
                'group_by': 'numerodepartement, ville, familleavis',
            }))
            open(cf, 'wb').write(gzip.compress(json.dumps(res).encode()))
        mi = (y - 2025) * 12 + mo - 1
        acc = {}
        for r in res:
            d = dep_of(r.get('numerodepartement'))
            if d is None:
                continue
            f = FAMS.index(r.get('familleavis')) if r.get('familleavis') in FAMS else FAMS.index('autre')
            c = geocode(d, r.get('ville'))
            k = (d, c, f)
            acc[k] = acc.get(k, 0) + int(r.get('n') or 0)
        for (d, c, f), n in acc.items():
            agg['m'].append(mi); agg['d'].append(d); agg['c'].append(c); agg['f'].append(f); agg['n'].append(n)

    # 2) Annonces une par une, pour les statuts détaillés
    print('2/2  Annonces une par une (' + ', '.join(detail) + ')…', flush=True)
    dicts = {'acts': [], 'nat': [], 'cat': [], 'rm': [], 'dt': []}
    didx = {k: {} for k in dicts}
    def put(name, s):
        s = (s or '').strip()
        if not s:
            return -1
        m_ = didx[name]
        if s not in m_:
            m_[s] = len(dicts[name]); dicts[name].append(s)
        return m_[s]
    cols = {k: [] for k in ['id', 'j', 'f', 'd', 'c', 'n', 'a', 'nat', 'cat', 'rt', 'rm', 'ml', 'dt', 'cl', 'k']}
    semaines = []
    s = d0
    while s <= d1:
        e = min(s + dt.timedelta(days=6), d1)
        semaines.append((s, e)); s = e + dt.timedelta(days=1)
    total_req = len(semaines) * len(detail)
    k_req = 0
    for code in detail:
        fi = FAMS.index(code)
        select = 'id,dateparution,numerodepartement,ville,registre,' + CHAMPS[code]
        for (s, e) in semaines:
            k_req += 1
            cf = os.path.join(cache, f'rows2_{code}_{s}_{e}.json.gz')
            if os.path.exists(cf) and e < recent:
                recs = json.loads(gzip.decompress(open(cf, 'rb').read()))
            else:
                print(f'  [{k_req}/{total_req}] {code} {s} → {e}', flush=True)
                where = f'familleavis="{code}" and dateparution>=date\'{s}\' and dateparution<=date\'{e}\''
                raw = rows_of(get_json('/exports/json', {'select': select, 'where': where}))
                recs = []
                for r in raw:
                    le = parse(r.get('listeetablissements'))
                    et = le.get('etablissement') if isinstance(le, dict) else None
                    if isinstance(et, list): et = et[0] if et else None
                    act = str(et.get('activite')).strip() if isinstance(et, dict) and et.get('activite') else ''
                    jug = parse(r.get('jugement'))
                    acte = parse(r.get('acte'))
                    rad = parse(r.get('radiationaurcs'))
                    mod = parse(r.get('modificationsgenerales'))
                    dep_ = parse(r.get('depot'))
                    rec = {
                        'id': r.get('id'), 'date': str(r.get('dateparution') or '')[:10], 'dep': r.get('numerodepartement'),
                        'ville': r.get('ville'), 'siren': siren_of(r.get('registre')), 'act': act,
                        'nat': get_key(jug, ['nature', 'famille']) or (get_key(acte, ['descriptif', 'categorieCreation']) if code in ('conciliation', 'retablissement_professionnel', 'divers') else ''),
                        'cat': get_key(acte, ['categorieImmatriculation', 'categorieCreation', 'categorieModification', 'categorieVente']) if code in ('immatriculation', 'creation') else '',
                        'rt': (1 if get_key(rad, ['radiationPM']) else 2 if get_key(rad, ['radiationPP']) else 0) if code == 'radiation' else 0,
                        'rm': '', 'ml': 0, 'dt': '', 'cl': 0, 'k': capital_of(r.get('listepersonnes')),
                    }
                    if code == 'radiation':
                        txt = norm(all_text(rad) + ' ' + all_text(acte))
                        rec['rm'] = next((lab for lab, rx in RAD_MOTIFS if re.search(rx, txt)), '')
                    if code == 'modification':
                        txt = norm(get_key(mod, ['descriptif']) or all_text(mod))
                        rec['ml'] = sum(1 << b for b, rx in enumerate(MODIF_RULES) if re.search(rx, txt))
                    if code == 'dpc' and isinstance(dep_, dict):
                        rec['dt'] = str(dep_.get('typeDepot') or get_key(dep_, ['typeDepot', 'descriptif']) or '')[:120]
                        dc = str(dep_.get('dateCloture') or '')
                        rec['cl'] = int(dc[5:7]) if re.match(r'^\d{4}-\d{2}', dc) else 0
                    recs.append(rec)
                open(cf, 'wb').write(gzip.compress(json.dumps(recs, ensure_ascii=False).encode()))
            for rec in recs:
                d = dep_of(rec['dep'])
                if d is None or not rec['date']:
                    continue
                if deps_filtre and deps[d][0] not in deps_filtre:
                    continue
                try:
                    j = (dt.date.fromisoformat(rec['date']) - J0).days
                except ValueError:
                    continue
                cols['id'].append(rec['id']); cols['j'].append(j); cols['f'].append(fi); cols['d'].append(d)
                cols['c'].append(geocode(d, rec['ville'])); cols['n'].append(rec['siren'])
                cols['a'].append(put('acts', rec['act'])); cols['nat'].append(put('nat', rec['nat'])); cols['cat'].append(put('cat', rec['cat']))
                cols['rt'].append(rec['rt']); cols['rm'].append(put('rm', rec['rm'])); cols['ml'].append(rec['ml'])
                cols['dt'].append(put('dt', rec['dt'])); cols['cl'].append(rec['cl']); cols['k'].append(rec.get('k', 0))

    # Tri par date (l’application lit les plus récentes en partant de la fin)
    order = sorted(range(len(cols['j'])), key=lambda i: cols['j'][i])
    for k in cols:
        cols[k] = [cols[k][i] for i in order]

    D['extra'] = {
        'version': 1, 'depuis': d0.isoformat(), 'jusqu': d1.isoformat(),
        'construit': dt.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'detail': detail, 'departements': sorted(deps_filtre),
        'agg': agg, 'rows': cols, 'dicts': dicts,
    }
    payload = base64.b64encode(gzip.compress(json.dumps(D, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), 9)).decode()
    html2 = html[:m.start(2)] + payload + html[m.end(2):]
    open(out_path, 'w', encoding='utf-8').write(html2)
    print(f'\nTerminé : {out_path}')
    fmt = lambda n: f'{n:,}'.replace(',', ' ')
    print(f'  {fmt(len(cols["j"]))} annonces détaillées, {fmt(len(agg["n"]))} lignes de volumes, fichier de {os.path.getsize(out_path) / 1e6:.1f} Mo')

if __name__ == '__main__':
    main()
