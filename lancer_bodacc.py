#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lance l’application BODACC sur votre machine et lui permet d’actualiser ses données.

Usage (dans le dossier qui contient annonces-bodacc-france.html et construire_base_bodacc.py) :
    python lancer_bodacc.py
Le navigateur s’ouvre sur http://localhost:8000. Laissez la fenêtre du terminal ouverte
pendant l’utilisation ; Ctrl+C pour arrêter.

Ce petit serveur fait trois choses :
  1. il sert l’application (la version complète si elle existe) ;
  2. il relaie les requêtes de l’application vers le BODACC : c’est Python qui interroge
     le BODACC, pas le navigateur, ce qui évite les blocages entre sites (CORS) ;
  3. il lance la reconstruction de la base complète quand vous cliquez sur
     « Actualiser la base » dans l’application, et affiche l’avancement.
Seule la bibliothèque standard de Python (3.8+) est utilisée.
"""
import json, os, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get('BODACC_PORT', '8000'))
DOSSIER = os.path.dirname(os.path.abspath(__file__))
HOTES = [h for h in os.environ.get('BODACC_HOTES', '').split(',') if h] or [
    'https://www.bodacc.fr/api/explore/v2.1/catalog/datasets/annonces-commerciales',
    'https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales',
]
BASE = 'annonces-bodacc-france.html'
COMPLET = 'annonces-bodacc-france-complet.html'
SOURCE = {'hote': None, 'erreur': None}
TACHE = {'en_cours': False, 'lignes': [], 'fin': None, 'code': None, 'debut': None}


def appel(chemin_et_requete, timeout=600):
    """Interroge le BODACC en essayant chaque adresse connue ; retient celle qui répond."""
    hotes = ([SOURCE['hote']] if SOURCE['hote'] else []) + [h for h in HOTES if h != SOURCE['hote']]
    derniere = None
    for h in hotes:
        url = h + chemin_et_requete
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'lancer-bodacc/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                corps = r.read()
                SOURCE['hote'] = h; SOURCE['erreur'] = None
                return r.status, r.headers.get('Content-Type', 'application/json'), corps
        except urllib.error.HTTPError as e:
            corps = e.read()
            if e.code == 400:            # requête refusée : inutile d’essayer une autre adresse
                SOURCE['hote'] = h
                return 400, 'application/json', corps
            derniere = f'{h} : HTTP {e.code}'
        except Exception as e:
            derniere = f'{h} : {e}'
    SOURCE['erreur'] = derniere
    raise RuntimeError(derniere)


def diagnostic():
    print('Test de connexion au BODACC…', flush=True)
    try:
        code, _, corps = appel('/records?limit=1&select=id,dateparution&order_by=dateparution%20desc', timeout=60)
        j = json.loads(corps.decode('utf-8'))
        der = (j.get('results') or [{}])[0].get('dateparution', '?')
        print(f'  BODACC joignable via {SOURCE["hote"].split("/api")[0]} — dernière annonce publiée : {der}', flush=True)
    except Exception as e:
        print('  ÉCHEC : le BODACC ne répond pas depuis cette machine.', flush=True)
        print(f'  Détail : {e}', flush=True)
        print('  Vérifiez la connexion internet, un éventuel proxy d’entreprise ou un pare-feu.', flush=True)


def reconstruire(options):
    TACHE.update(en_cours=True, lignes=[], fin=None, code=None, debut=time.time())
    cmd = [sys.executable, '-u', os.path.join(DOSSIER, 'construire_base_bodacc.py'), '--html', os.path.join(DOSSIER, BASE),
           '--sortie', os.path.join(DOSSIER, COMPLET)]
    if options.get('departements'):
        cmd += ['--departements', options['departements']]
    if options.get('depuis'):
        cmd += ['--depuis', options['depuis']]
    if options.get('tout'):
        cmd += ['--tout']
    env = dict(os.environ)
    if SOURCE['hote']:
        env['BODACC_API'] = SOURCE['hote']
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=env, cwd=DOSSIER)
        for ligne in p.stdout:
            ligne = ligne.rstrip()
            if ligne:
                print('  [base] ' + ligne, flush=True)
                TACHE['lignes'] = (TACHE['lignes'] + [ligne])[-200:]
        TACHE['code'] = p.wait()
    except Exception as e:
        TACHE['lignes'].append(f'Erreur : {e}'); TACHE['code'] = 1
    TACHE.update(en_cours=False, fin=time.time())


class Gestionnaire(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DOSSIER, **k)

    def log_message(self, fmt, *args):
        pass

    def envoyer(self, code, corps, type_='application/json; charset=utf-8'):
        if isinstance(corps, (dict, list)):
            corps = json.dumps(corps, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', type_)
        self.send_header('Content-Length', str(len(corps)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path in ('/', '/index.html'):
            cible = COMPLET if os.path.exists(os.path.join(DOSSIER, COMPLET)) else BASE
            self.send_response(302); self.send_header('Location', '/' + cible); self.end_headers(); return
        if u.path == '/relais/etat':
            return self.envoyer(200, {'relais': True, 'hote': SOURCE['hote'], 'erreur': SOURCE['erreur'], 'complet': os.path.exists(os.path.join(DOSSIER, COMPLET)),
                                      'reconstruction': {k: TACHE[k] for k in ('en_cours', 'code', 'debut', 'fin')}, 'journal': TACHE['lignes'][-6:]})
        if u.path.startswith('/relais/bodacc/'):
            reste = u.path[len('/relais/bodacc'):] + ('?' + u.query if u.query else '')
            try:
                code, type_, corps = appel(reste)
                return self.envoyer(code, corps, type_)
            except Exception as e:
                return self.envoyer(502, {'erreur': str(e)})
        return super().do_GET()

    def do_POST(self):
        if self.path == '/relais/actualiser':
            n = int(self.headers.get('Content-Length') or 0)
            try:
                options = json.loads(self.rfile.read(n) or b'{}')
            except Exception:
                options = {}
            if TACHE['en_cours']:
                return self.envoyer(409, {'erreur': 'Une actualisation est déjà en cours.'})
            threading.Thread(target=reconstruire, args=(options,), daemon=True).start()
            return self.envoyer(202, {'ok': True})
        self.envoyer(404, {'erreur': 'inconnu'})


def main():
    if not os.path.exists(os.path.join(DOSSIER, BASE)):
        sys.exit(f'{BASE} est introuvable : placez ce script dans le même dossier.')
    diagnostic()
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Gestionnaire)
    url = f'http://localhost:{PORT}/'
    print(f'\nApplication disponible sur {url}  (Ctrl+C pour arrêter)', flush=True)
    if not os.environ.get('BODACC_SANS_NAVIGATEUR'):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nArrêt.')


if __name__ == '__main__':
    main()
