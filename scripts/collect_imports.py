import os,sys,re
root='.'
imports=set()
for dirpath,dirs,files in os.walk(root):
    if '.git' in dirpath or 'node_modules' in dirpath or 'venv' in dirpath:
        continue
    for f in files:
        if f.endswith('.py'):
            p=os.path.join(dirpath,f)
            try:
                with open(p,'r',encoding='utf-8') as fh:
                    for line in fh:
                        m=re.match(r"\s*from\s+([\w\.]+)\s+import",line)
                        if m: imports.add(m.group(1).split('.')[0])
                        m=re.match(r"\s*import\s+([\w\.]+)",line)
                        if m:
                            imports.add(m.group(1).split('.')[0])
            except Exception:
                pass
stdlib=set(sys.builtin_module_names)
stdlib.update(['os','re','sys','json','time','math','logging','pathlib','itertools','collections','typing','threading','subprocess','http','unittest','dataclasses','functools','heapq','glob','hashlib','argparse','shutil','tempfile','uuid','signal','inspect','enum','base64','email'])
st_map={
 'flask':'Flask','flask_cors':'flask-cors','chromadb':'chromadb','openai':'openai','requests':'requests','pandas':'pandas','numpy':'numpy','scikit-learn':'scikit-learn','sklearn':'scikit-learn','xgboost':'xgboost','lightgbm':'lightgbm','shap':'shap','radon':'radon','sqlalchemy':'SQLAlchemy','gunicorn':'gunicorn'
}
reqs=[]
for imp in sorted(imports):
    if imp in stdlib: continue
    name=imp
    if imp in st_map:
        name=st_map[imp]
    # avoid project modules (ml, models, scripts)
    if os.path.isdir(os.path.join('.', imp)):
        continue
    reqs.append(name)
for r in reqs:
    print(r)
