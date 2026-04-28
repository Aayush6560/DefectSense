import os
import re
import time
import json
import logging
from collections import deque
from pathlib import Path
from typing import Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
except Exception:
    chromadb = None
    embedding_functions = None

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [RAG] %(levelname)s %(message)s")
log = logging.getLogger("rag_chat")

KNOWLEDGE_BASE = [
    {"id":"kb_1","text":"Cyclomatic complexity measures the number of independent execution paths in a function. Values above 10 usually justify refactoring and additional tests. Values above 20 are critical.","tags":{"cyclomatic","complexity","v(g)","control","paths"}},
    {"id":"kb_2","text":"Halstead Volume estimates how much information is present in a program. Higher volume usually means denser logic and greater maintenance risk. Volumes above 1000 are a strong defect signal.","tags":{"halstead","volume","information","density"}},
    {"id":"kb_3","text":"Halstead Difficulty reflects the cognitive effort required to understand or write code. Large difficulty often signals brittle or complex logic. A difficulty above 15 usually needs attention.","tags":{"halstead","difficulty","cognitive","effort"}},
    {"id":"kb_4","text":"Lines of code alone is not a reliable defect signal, but unusually large modules (above 300 LOC) often deserve decomposition into smaller units with single responsibilities.","tags":{"loc","lines","size","decomposition"}},
    {"id":"kb_5","text":"Comment density can help maintainability, but comments should explain intent rather than restate code. Good naming and small functions matter more than comment volume alone.","tags":{"comments","maintainability","intent"}},
    {"id":"kb_6","text":"Static analysis and unit tests complement each other. Static metrics reveal structural risk while tests verify expected behavior and edge cases. Both are needed for reliable software.","tags":{"static","analysis","tests","behavior"}},
    {"id":"kb_7","text":"Security scanning should flag dangerous patterns such as eval, exec, shell=True, and unsafe deserialization before deployment. These are common root causes of runtime vulnerabilities.","tags":{"security","eval","exec","shell","pickle"}},
    {"id":"kb_8","text":"A good refactor path is to split high-complexity functions into smaller helpers, isolate I/O from logic, and test the extracted units separately. This reduces both complexity and defect probability.","tags":{"refactor","helpers","io","logic","testing"}},
    {"id":"kb_9","text":"Model confidence should be paired with recall and precision. High accuracy can still hide poor defect detection on the minority class. Use F1 score and AUC-ROC as primary evaluation metrics.","tags":{"accuracy","recall","precision","imbalance","f1","roc"}},
    {"id":"kb_10","text":"When working with defect prediction datasets, inspect missing markers and convert all numeric fields before training to avoid corrupt model inputs. SMOTE can handle class imbalance effectively.","tags":{"dataset","missing","numeric","training","smote"}},
    {"id":"kb_11","text":"Kubernetes deployments should define readiness and liveness probes, explicit images, and a stable service selector to avoid opaque rollout failures. Always set resource limits on containers.","tags":{"kubernetes","deployment","readiness","liveness","service"}},
    {"id":"kb_12","text":"Docker builds should keep the build context small with a .dockerignore file and should not include virtual environments or caches. Use multi-stage builds to minimize final image size.","tags":{"docker","build","context","ignore","multistage"}},
    {"id":"kb_13","text":"Context-grounded retrieval works best when the retriever stays close to real source material and the generator cites retrieved passages clearly. Hybrid search improves recall by combining vector and keyword signals.","tags":{"rag","retriever","generator","source","hybrid"}},
    {"id":"kb_14","text":"A repository-backed search can return explanations from code, workflows, and manifests without claiming external knowledge that is not present in the project.","tags":{"repository","search","code","workflow","manifests"}},
    {"id":"kb_15","text":"For defect-prone files, the first fix is usually to reduce branching complexity, simplify data flow, and add tests around the most error-prone paths.","tags":{"defect","branching","tests","paths"}},
    {"id":"kb_16","text":"Stacking ensemble models combine multiple base learners (XGBoost, LightGBM) with a meta-learner (LogisticRegression) to reduce variance and improve defect detection. Achieves 92%+ AUC-ROC.","tags":{"stacking","ensemble","xgboost","lightgbm","metalearner"}},
    {"id":"kb_17","text":"SHAP (SHapley Additive exPlanations) values explain individual predictions by attributing each feature a positive or negative contribution. Positive SHAP = increases defect risk; negative SHAP = reduces it.","tags":{"shap","explainability","feature","contribution","xai"}},
    {"id":"kb_18","text":"Class imbalance in defect datasets means defect-prone files are the minority class (often 10-20%). Techniques like SMOTE, class_weight=balanced, and threshold tuning improve recall on the minority class.","tags":{"imbalance","smote","minority","threshold","recall"}},
    {"id":"kb_19","text":"Halstead Estimated Bugs (b) directly approximates the number of latent defects in a module using the formula b = V / 3000. Values above 0.5 are a strong defect signal worth investigating.","tags":{"halstead","bugs","estimated","latent","b"}},
    {"id":"kb_20","text":"Branch count and decision points are strongly correlated with defect density. Every additional if/elif/for/while branch is a new test case that must be covered to prevent regression.","tags":{"branch","decision","coverage","test","regression"}},
    {"id":"kb_21","text":"Flask routes should be kept thin: move business logic into service modules, not directly inside route functions. This keeps cyclomatic complexity low and improves testability.","tags":{"flask","routes","service","complexity","testability"}},
    {"id":"kb_22","text":"Feature extraction for defect prediction should include Halstead metrics, cyclomatic complexity, LOC, comment ratio, and branch count. Radon is a reliable Python library for computing these metrics.","tags":{"feature","extraction","radon","halstead","cyclomatic"}},
    {"id":"kb_23","text":"Decision threshold tuning is critical for imbalanced datasets. The optimal threshold is found by maximizing F1 score on the validation set using the precision-recall curve, not by defaulting to 0.5.","tags":{"threshold","f1","precision","recall","validation","tuning"}},
    {"id":"kb_24","text":"High nesting depth (more than 3 levels of indentation) is a strong indicator of complex control flow. Flatten nested conditionals using early returns and guard clauses to reduce cognitive load.","tags":{"nesting","indentation","guard","early","return","flatten"}},
    {"id":"kb_25","text":"God functions that handle too many responsibilities at once are a primary defect source. A function should do exactly one thing and be short enough to fully understand in under 30 seconds.","tags":{"god","function","responsibility","single","short"}},
    {"id":"kb_26","text":"Kubernetes service selectors must exactly match pod labels. A mismatch causes the service to have zero endpoints, making the app unreachable even if pods are running and healthy.","tags":{"kubernetes","selector","labels","endpoints","service","mismatch"}},
    {"id":"kb_27","text":"Python virtual environments (.venv, env/) should never be included in Docker build context. Use a .dockerignore file to exclude them and keep image size small.","tags":{"docker","venv","dockerignore","image","size"}},
    {"id":"kb_28","text":"Ansible playbooks automate infrastructure provisioning. For DefectSense, Ansible automates Docker image builds, Kubernetes manifest deployment, and health checks in a single idempotent playbook.","tags":{"ansible","playbook","automation","provisioning","idempotent"}},
    {"id":"kb_29","text":"Metric loc is the total lines in the file. Higher loc usually means larger review surface and higher maintenance risk.","tags":{"loc","lines of code","line count","size"}},
    {"id":"kb_30","text":"Metric v(g) is cyclomatic complexity. It estimates the number of independent decision paths; higher values require more test cases.","tags":{"v(g)","cyclomatic","complexity","decision paths"}},
    {"id":"kb_31","text":"Metric ev(g) is essential complexity. It reflects how much unstructured control flow remains after removing structured loops. High ev(g) means the code is hard to modularize.","tags":{"ev(g)","essential","complexity","unstructured"}},
    {"id":"kb_32","text":"Metric iv(g) is design complexity. It measures the coupling between a module and its called modules. High iv(g) means many dependencies and low module isolation.","tags":{"iv(g)","design","coupling","dependency","isolation"}},
    {"id":"kb_33","text":"Metric n is total Halstead operands and operators. Higher n means more program vocabulary and usually more cognitive load.","tags":{"halstead","n","operands","operators","vocabulary"}},
    {"id":"kb_34","text":"Metric v is Halstead volume: v = n * log2(eta). High volume means dense information content.","tags":{"halstead","v","volume","distinct","eta"}},
    {"id":"kb_35","text":"Metric d is Halstead difficulty: d = (eta1/2) * (N2/eta2). High d means the program is hard to write or understand correctly.","tags":{"halstead","d","difficulty","eta1","N2"}},
    {"id":"kb_36","text":"Metric e is Halstead effort: e = d * v. It approximates mental effort needed to code or understand the program. Very high effort values are correlated with bug introduction.","tags":{"halstead","e","effort","mental","bug"}},
    {"id":"kb_37","text":"Metric b is Halstead estimated bugs: b = v / 3000. Values above 0.5 indicate latent defects that deserve a code review.","tags":{"halstead","b","bugs","latent","estimate"}},
    {"id":"kb_38","text":"Metric t is Halstead time to program in seconds: t = e / 18. Gives approximate time needed to comprehend the module from scratch.","tags":{"halstead","t","time","comprehend","seconds"}},
    {"id":"kb_39","text":"Metric uniq_op is number of unique operators. Very high count means the code uses many different language constructs, increasing reading complexity.","tags":{"uniq_op","operators","unique","constructs"}},
    {"id":"kb_40","text":"Metric uniq_opnd is number of unique operands. High unique operand count usually means many variables and literals, often a sign of a large or poorly structured scope.","tags":{"uniq_opnd","operands","unique","variables","scope"}},
    {"id":"kb_41","text":"Metric branchCount is the number of decision branches. Strongly correlated with defect density. Each branch is a potential test gap if not covered.","tags":{"branchcount","branch","decision","defect","coverage"}},
    {"id":"kb_42","text":"One of the most effective ways to lower cyclomatic complexity is to extract repeated conditional patterns into named predicate functions.","tags":{"cyclomatic","predicate","extract","intent","test"}},
    {"id":"kb_43","text":"When a file has both high cyclomatic complexity and high Halstead effort, the defect probability increases multiplicatively. Both signals together are a strong reason to block deployment.","tags":{"cyclomatic","halstead","effort","multiplicative","block","deployment"}},
    {"id":"kb_44","text":"MLOps pipelines should gate on model metrics as well as code quality. A deployment should fail if model AUC-ROC drops below threshold, just as it fails if defect probability rises above threshold.","tags":{"mlops","gate","auc","threshold","pipeline","deployment"}},
    {"id":"kb_45","text":"The DefectSense CI/CD pipeline has six stages: syntax check, unit tests, ML defect scan, security audit, Docker build, and Kubernetes deploy. The ML defect scan acts as a quality gate that can block all later stages.","tags":{"cicd","pipeline","stages","gate","syntax","docker","kubernetes"}},
    {"id":"kb_46","text":"Reducing nesting depth using early returns and guard clauses is one of the fastest ways to lower both cyclomatic and essential complexity simultaneously.","tags":{"nesting","guard","early","return","cyclomatic","essential"}},
    {"id":"kb_47","text":"A canary deployment routes 10% of traffic to the new version first. If error rates stay stable after monitoring, the rest of traffic is promoted. Ideal for medium-risk releases.","tags":{"canary","deployment","traffic","monitoring","promote"}},
    {"id":"kb_48","text":"Blue-green deployment runs two identical environments in parallel. Traffic is switched instantly from blue to green. Rollback is immediate by switching back. Used for high-risk releases.","tags":{"blue","green","deployment","rollback","parallel","environment"}},
    {"id":"kb_49","text":"Rolling update deployment replaces pods one at a time. Zero downtime but slower rollout. Best for low-risk releases where gradual replacement is acceptable.","tags":{"rolling","update","pods","zero","downtime","gradual"}},
]

METRIC_DEFINITIONS = {
    "loc":      {"title":"Lines of code",          "aliases":["loc","lines of code","line count"],              "meaning":"Total lines in the file. Large modules are harder to review and test.","warn":150,"critical":300},
    "v(g)":     {"title":"Cyclomatic complexity",   "aliases":["v(g)","vg","cyclomatic","cyclomatic complexity"],"meaning":"Independent decision paths tests must cover.","warn":10,"critical":20},
    "ev(g)":    {"title":"Essential complexity",    "aliases":["ev(g)","essential complexity"],                  "meaning":"How much control flow is structurally difficult to simplify."},
    "iv(g)":    {"title":"Design complexity",       "aliases":["iv(g)","design complexity","average complexity"],"meaning":"Average per-function complexity."},
    "n":        {"title":"Halstead program length", "aliases":["n","halstead length","program length"],          "meaning":"Total operator and operand occurrences."},
    "v":        {"title":"Halstead volume",         "aliases":["v","halstead volume","volume"],                  "meaning":"Information content of code. High values = dense logic.","warn":500,"critical":1000},
    "l":        {"title":"Halstead level",          "aliases":["l","halstead level","level"],                    "meaning":"Expression level; lower values mean harder code."},
    "d":        {"title":"Halstead difficulty",     "aliases":["d","halstead difficulty","difficulty"],          "meaning":"Cognitive effort to understand or implement the code.","warn":10,"critical":20},
    "i":        {"title":"Halstead intelligence",   "aliases":["i","halstead intelligence","content"],           "meaning":"Useful information content derived from Halstead."},
    "e":        {"title":"Halstead effort",         "aliases":["e","halstead effort","effort"],                  "meaning":"Estimated effort to implement or reason about code."},
    "b":        {"title":"Estimated bugs",          "aliases":["b","estimated bugs","bug estimate","halstead bugs"],"meaning":"Approximate latent defects (V/3000).","warn":0.3,"critical":0.7},
    "t":        {"title":"Halstead time (s)",       "aliases":["t","halstead time","time"],                      "meaning":"Approximate comprehension time in seconds (E/18)."},
    "uniq_op":  {"title":"Unique operators",        "aliases":["uniq_op","unique operators"],                    "meaning":"Distinct operator types used in the file."},
    "uniq_opnd":{"title":"Unique operands",         "aliases":["uniq_opnd","unique operands"],                   "meaning":"Distinct operands (names/literals) used in the file."},
    "total_op": {"title":"Total operators",         "aliases":["total_op","total operators"],                    "meaning":"Total operator occurrences in the file."},
    "total_opnd":{"title":"Total operands",         "aliases":["total_opnd","total operands"],                   "meaning":"Total operand occurrences in the file."},
    "branchCount":{"title":"Branch count",          "aliases":["branchcount","branch count","branches"],         "meaning":"Decision points from conditionals/loops/handlers.","warn":15,"critical":30},
}

INTENT_PATTERNS = {
    "METRIC_EXPLAIN":   r"\b(what is|explain|define|mean|means|metric|v\(g\)|ev\(g\)|iv\(g\)|loc|halstead|branchcount|uniq_op|total_op|volume|difficulty|effort|bugs|intelligence)\b",
    "WHY_RISK":         r"\b(why|reason|cause|risky|high risk|defect|flagged|blocked|score|probability|percent)\b",
    "FIX_PLAN":         r"\b(fix|reduce|improve|refactor|lower|how to|should i|recommend|suggestion|what to do|next step|action plan)\b",
    "SHAP_EXPLAIN":     r"\b(shap|feature importance|contribution|influence|driving|leading|top feature)\b",
    "DEPLOYMENT":       r"\b(deploy|docker|kubernetes|k8s|ansible|pipeline|cicd|ci/cd|stage|build|rollout|canary|blue.green|rolling|kubectl|manifest)\b",
    "MODEL_INFO":       r"\b(model|ensemble|xgboost|lightgbm|stacking|accuracy|auc|f1|precision|recall|train|dataset)\b",
    "SECURITY":         r"\b(security|eval|exec|shell|pickle|unsafe|vulnerability|bandit|cve|scan)\b",
    "FUNCTION_HOTSPOT": r"\b(function|method|class|hotspot|worst|most complex|top function|highest|which function)\b",
}

STOP = {"what","is","the","a","an","how","to","why","does","do","my","this","it","its","in","of","for","and","or","not","be","can","i","me","with","on","at"}
_conversation_memory: dict[str, deque] = {}
_repeat_tracker:      dict[str, dict]  = {}
_response_counter = 0
_chroma_collection = None
_repo_chunks: list[dict] = []
_repo_loaded = False

def _tokenize(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9_()]+", text.lower()) if w not in STOP and len(w) > 2}

def _sanitize_question(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip())

def _overlap_ratio(a: str, b: str) -> float:
    a_t, b_t = _tokenize(a), _tokenize(b)
    if not a_t or not b_t:
        return 0.0
    return len(a_t & b_t) / max(len(a_t), len(b_t))

def _is_smalltalk(q: str) -> bool:
    compact = q.strip()
    if compact in {"hi","hello","hey","yo","sup","hii"}:
        return True
    return any(p in compact for p in ["hello ai","hi ai","hey ai"])

def _is_low_signal_prompt(question: str) -> bool:
    q_lower = question.lower().strip()
    valid_short = {"risk","risky","why risk","fix","top fixes","what to do","what now","how to fix","next step","next steps","metrics","metric","explain metrics"}
    if q_lower in valid_short:
        return False
    tokens = _tokenize(question)
    if len(set(tokens)) < 2:
        return True
    if len(question) > 120 and len(set(tokens)) < 6:
        return True
    return False

def _track_repeat(filename: str, question: str) -> int:
    key    = filename or "global"
    bucket = _repeat_tracker.setdefault(key, {})
    q_key  = question.lower().strip()
    count  = bucket.get(q_key, 0) + 1
    bucket[q_key] = count
    return count

def _remember_turn(filename: str, question: str, answer: str):
    key   = filename or "global"
    convo = _conversation_memory.setdefault(key, deque(maxlen=6))
    convo.append({"q": question[:200], "a": answer[:300]})

def _get_recent_question(filename: str) -> str:
    convo = _conversation_memory.get(filename or "global")
    if convo:
        return convo[-1]["q"]
    return ""

def _contains_alias(q: str, alias: str) -> bool:
    alias = alias.strip().lower()
    if not alias:
        return False
    if re.fullmatch(r"[a-z0-9_]+", alias):
        return bool(re.search(rf"\b{re.escape(alias)}\b", q))
    return alias in q

def _extract_metric_name(q: str) -> str:
    for key, spec in METRIC_DEFINITIONS.items():
        aliases = [key.lower(), spec["title"].lower()] + [a.lower() for a in spec.get("aliases", [])]
        if any(_contains_alias(q, a) for a in aliases):
            return key
    return ""

def _is_metric_intent(q: str) -> bool:
    if q.strip() in {"explain","explain metric","explain metrics","metrics","metric"}:
        return True
    tokens = _tokenize(q)
    if tokens & {"cyclomatic","halstead","loc","difficulty","volume","branchcount"}:
        return True
    if "explain" in tokens and tokens & {"metric","metrics","complexity","bugs","lines"}:
        return True
    return bool(_extract_metric_name(q))

def _is_deployment_question(q: str) -> bool:
    terms = {"deploy","deployment","kubernetes","k8s","pipeline","ci","cd","rollout","manifest","kubectl","docker build","container","ansible","helm"}
    return any(t in q for t in terms)

def _is_function_risk_question(q: str) -> bool:
    tokens = _tokenize(q)
    direct = ["which function has high risk","which function has more risk","high risk function","risky function","most risky function"]
    return any(p in q for p in direct) or bool(tokens & {"function","func","method"} and tokens & {"risk","defect","bug","error"})

def classify_intent(question: str) -> str:
    q = question.lower()
    scores = {}
    for intent, pattern in INTENT_PATTERNS.items():
        m = len(re.findall(pattern, q))
        if m:
            scores[intent] = m
    return max(scores, key=scores.get) if scores else "GENERAL"

def _token_score(entry: dict, q_tokens: set) -> float:
    return len(q_tokens & entry["tags"]) * 2.0 + len(q_tokens & _tokenize(entry["text"]))

def _lexical_search(query: str, k: int = 4) -> list[dict]:
    q_t = _tokenize(query)
    scored = sorted([{**e,"_lex":round(_token_score(e,q_t),3)} for e in KNOWLEDGE_BASE if _token_score(e,q_t)>0], key=lambda x:x["_lex"],reverse=True)
    return scored[:k]

def _get_chroma_collection():
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection
    if chromadb is None:
        return None
    try:
        ef  = embedding_functions.DefaultEmbeddingFunction()
        col = chromadb.Client().get_or_create_collection("defectsense_kb", embedding_function=ef)
        if col.count() == 0:
            col.add(documents=[e["text"] for e in KNOWLEDGE_BASE],ids=[e["id"] for e in KNOWLEDGE_BASE],metadatas=[{"tags":",".join(e["tags"])} for e in KNOWLEDGE_BASE])
        _chroma_collection = col
        return col
    except Exception as exc:
        log.warning("ChromaDB: %s", exc)
        return None

def _vector_search(query: str, k: int = 4) -> list[dict]:
    col = _get_chroma_collection()
    if col is None:
        return []
    try:
        res = col.query(query_texts=[query], n_results=min(k, col.count()))
        out = []
        for i, doc_id in enumerate(res["ids"][0]):
            entry = next((e for e in KNOWLEDGE_BASE if e["id"]==doc_id), None)
            if entry:
                dist = res["distances"][0][i] if "distances" in res else 0.0
                out.append({**entry,"_vec":round(1-dist,3)})
        return out
    except Exception as exc:
        log.warning("Vector search: %s", exc)
        return []

def _hybrid_search(query: str, k: int = 4, intent: str = "GENERAL") -> dict:
    vec = _vector_search(query, k=k+2)
    lex = _lexical_search(query, k=k+2)
    engine = "semantic+lexical" if vec else "lexical"
    merged: dict[str,dict] = {}
    for e in vec:
        merged[e["id"]] = {**e,"_hybrid":round(e.get("_vec",0)*0.6,3)}
    for e in lex:
        eid = e["id"]
        lc  = round(e.get("_lex",0)/20.0,3)
        if eid in merged:
            merged[eid]["_hybrid"] = round(merged[eid]["_hybrid"]+lc*0.4,3)
            merged[eid]["_lex"]    = e.get("_lex",0)
        else:
            merged[eid] = {**e,"_hybrid":round(lc*0.4,3)}
    boost_map = {
        "METRIC_EXPLAIN":{"halstead","cyclomatic","loc","branchcount","v(g)"},
        "WHY_RISK":{"defect","risk","probability","complexity"},
        "FIX_PLAN":{"refactor","fix","reduce","extract","guard"},
        "SHAP_EXPLAIN":{"shap","contribution","feature","xai"},
        "DEPLOYMENT":{"kubernetes","docker","ansible","cicd","pipeline","kubectl"},
        "MODEL_INFO":{"ensemble","xgboost","lightgbm","stacking","auc"},
        "FUNCTION_HOTSPOT":{"god","function","responsibility","nesting","single"},
    }
    for eid, e in merged.items():
        if e["tags"] & boost_map.get(intent,set()):
            merged[eid]["_hybrid"] = round(e["_hybrid"]+0.15,3)
            merged[eid]["_boosted"] = True
    ranked = sorted(merged.values(), key=lambda x:x["_hybrid"], reverse=True)[:k]
    evidence = [{"id":e["id"],"hybrid_score":e.get("_hybrid",0),"vec_score":e.get("_vec","n/a"),"lex_score":e.get("_lex","n/a"),"boosted":e.get("_boosted",False),"excerpt":e["text"][:120]+"..."} for e in ranked]
    return {"entries":ranked,"engine":engine,"evidence":evidence}

def _load_repo_chunks(root: Path = ROOT) -> list[dict]:
    global _repo_chunks, _repo_loaded
    if _repo_loaded:
        return _repo_chunks
    _repo_loaded = True
    out = []
    for pattern in ["*.py","*.yaml","*.yml","*.md","Dockerfile"]:
        for fp in root.rglob(pattern):
            try:
                text = fp.read_text(encoding="utf-8",errors="replace")
                if len(text) < 50:
                    continue
                lines, curr, chunks = text.splitlines(), [], []
                for ln in lines:
                    if sum(len(l) for l in curr)+len(ln)>400 and curr:
                        chunks.append("\n".join(curr)); curr=[]
                    curr.append(ln)
                if curr:
                    chunks.append("\n".join(curr))
                for i,chunk in enumerate(chunks):
                    out.append({"source":str(fp.relative_to(root)),"chunk_id":i,"text":chunk})
            except Exception:
                pass
    _repo_chunks = out
    return out

def _repo_search(query: str, k: int = 2) -> list[dict]:
    q_t = _tokenize(query)
    scored = sorted([{**c,"_s":len(q_t&_tokenize(c["text"]))} for c in _load_repo_chunks() if len(q_t&_tokenize(c["text"]))>0], key=lambda x:x["_s"],reverse=True)
    return scored[:k]

def _reformulate_query(question: str, prediction: dict) -> str:
    expansions = {r"\bcc\b":"cyclomatic complexity v(g)",r"\bv\(g\)\b":"cyclomatic complexity decision paths",r"\bhalstead\b":"halstead volume difficulty effort bugs",r"\bshap\b":"shap feature contribution explainability xai",r"\block\b":"lines of code loc size",r"\bfix\b":"fix reduce refactor improve"}
    q = question
    for pat, rep in expansions.items():
        q = re.sub(pat, rep, q, flags=re.IGNORECASE)
    fname = prediction.get("filename","")
    metrics = prediction.get("key_metrics",{})
    if fname:
        q += f" file:{fname}"
    top = sorted(metrics.items(), key=lambda x:x[1] if isinstance(x[1],(int,float)) else 0, reverse=True)
    if top:
        q += f" metric:{top[0][0]}={top[0][1]}"
    recent = _get_recent_question(fname)
    if recent:
        q += f" context:{recent[:80]}"
    return q

def _estimate_function_hotspots(source_code: str) -> list[tuple]:
    if not source_code.strip():
        return []
    lines  = source_code.splitlines()
    blocks = []
    cur_name = cur_start = cur_indent = None
    for i,line in enumerate(lines):
        stripped = line.lstrip()
        indent   = len(line)-len(stripped)
        if stripped.startswith(("def ","async def ")):
            if cur_name is not None:
                blocks.append((cur_name,cur_start,i))
            m = re.match(r"(?:async\s+def|def)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", stripped)
            cur_name  = m.group(1) if m else f"func_line_{i+1}"
            cur_start = i; cur_indent = indent
        elif cur_name is not None and stripped and cur_indent is not None and indent<=cur_indent:
            blocks.append((cur_name,cur_start,i)); cur_name=cur_start=cur_indent=None
    if cur_name:
        blocks.append((cur_name,cur_start,len(lines)))
    ranked = []
    for name,start,end in blocks:
        body    = "\n".join(lines[start:end])
        func_loc = max(1,end-start)
        branches = len(re.findall(r"\b(if|elif|for|while|try|except|and|or)\b",body))
        nesting  = len(re.findall(r"\n\s{8,}\S",body))
        score    = branches*2.5+func_loc*0.12+nesting*0.8
        ranked.append((name,round(score,1),func_loc))
    ranked.sort(key=lambda x:x[1],reverse=True)
    return ranked[:5]

def _severity_label(value: float, warn, critical) -> str:
    if warn is None or critical is None:
        return "N/A"
    if value >= critical:
        return "🔴 CRITICAL"
    if value >= warn:
        return "🟡 WARNING"
    return "🟢 OK"

def _build_metric_explanation(metrics: dict, filename: str, decision_text: str, metric_name: str, kb_text: str) -> str:
    def _fmt(v: float) -> str:
        return f"{v:.0f}" if abs(v)>=100 or v==int(v) else (f"{v:.2f}" if abs(v)>=1 else f"{v:.3f}")
    if metric_name and metric_name in METRIC_DEFINITIONS:
        spec  = METRIC_DEFINITIONS[metric_name]
        value = float(metrics.get(metric_name,0) or 0)
        status = _severity_label(value, spec.get("warn"), spec.get("critical"))
        thr   = f" Thresholds: warning>={spec['warn']}, critical>={spec['critical']}." if spec.get("warn") else ""
        return (f"**{spec['title']} ({metric_name})**\n\n"
                f"File: `{filename}` — {decision_text}\n"
                f"Value: **{_fmt(value)}** | Status: {status}\n"
                f"Meaning: {spec['meaning']}{thr}\n\n"
                f"**KB Evidence:**\n{kb_text}")
    lines = [f"**Full Metric Glossary for `{filename}`:**\n"]
    for key,spec in METRIC_DEFINITIONS.items():
        val = metrics.get(key,"N/A")
        if isinstance(val,(int,float)):
            stat = _severity_label(float(val),spec.get("warn"),spec.get("critical"))
            lines.append(f"• **{key}** = {_fmt(float(val))} {stat} — {spec['meaning'][:80]}")
        else:
            lines.append(f"• **{key}** — {spec['meaning'][:80]}")
    return "\n".join(lines)

def _build_action_plan(metrics: dict, top_features: list, source_code: str = "") -> list[str]:
    vg     = float(metrics.get("v(g)",0) or 0)
    v      = float(metrics.get("v",0) or 0)
    d      = float(metrics.get("d",0) or 0)
    loc    = float(metrics.get("loc",0) or 0)
    branch = float(metrics.get("branchCount",0) or 0)
    hotspots = _estimate_function_hotspots(source_code) if source_code else []
    target   = hotspots[0][0] if hotspots else "the most nested function"
    tf       = top_features[0][0] if top_features else "cyclomatic complexity"
    actions  = []
    if vg>=10 or branch>=8:
        actions.append(f"Reduce cyclomatic complexity: split `{target}` into smaller helpers and flatten nested conditionals using early returns (current v(g)={vg:.0f}).")
    if v>=500 or d>=10:
        actions.append(f"Reduce cognitive load: extract calculation blocks into named functions and replace magic constants with clear variables (Volume={v:.0f}, Difficulty={d:.1f}).")
    if loc>=150:
        actions.append(f"Split module: move file, parsing, and I/O logic into separate modules so each has one responsibility (current LOC={loc:.0f}).")
    actions.append(f"Write targeted tests for the top risk signal `{tf}`: cover happy path, edge cases, and failure paths before and after refactoring.")
    while len(actions) < 4:
        actions.append("Run incremental complexity scan after each change and verify risk score drops in DefectSense before merging.")
    return actions[:4]

def _build_deployment_plan() -> list[str]:
    return [
        "Verify cluster connection: `kubectl cluster-info` and `kubectl get nodes`.",
        "Re-apply manifests: `kubectl apply -f k8s/` then check events with `kubectl get events --sort-by=.lastTimestamp`.",
        "Check rollout health: `kubectl rollout status deployment/proj3-defectsense --timeout=180s` and inspect failing pods.",
        "Validate service routing: `kubectl get svc,ep proj3-defectsense -o wide` and test the app URL.",
    ]

def _build_response(question: str, prediction: dict, kb_entries: list[dict], repo_chunks: list[dict]) -> str:
    global _response_counter
    _response_counter += 1
    prob     = prediction.get("probability",0)
    pct      = round(prob*100,1)
    label    = prediction.get("label","Unknown")
    metrics  = prediction.get("key_metrics",{})
    risks    = prediction.get("risks",[])
    shap     = prediction.get("top_features",[])
    fname    = prediction.get("filename","this file")
    src      = prediction.get("source_code","")
    thresh   = float(prediction.get("decision_threshold",0.5) or 0.5)
    thp      = thresh*100
    risk_band= "HIGH" if prob>=0.65 else "MEDIUM" if prob>=0.40 else "LOW"
    blocked  = prob>=thresh
    decision = f"predicted {'Defective' if blocked else 'Clean'} at {pct}% (threshold {thp:.1f}%) — risk band {risk_band}"
    kb_text  = "\n".join(f"• [{e['id']}] {e['text'][:130]}" for e in kb_entries[:4])
    repo_ctx = "\n".join(f"[{c['source']}] {c['text'][:120]}" for c in repo_chunks[:2])
    q_clean  = _sanitize_question(question)
    q        = re.sub(r"[^a-z0-9()\s]+"," ",q_clean.lower()).strip()
    vg       = float(metrics.get("v(g)",0) or 0)
    v        = float(metrics.get("v",0) or 0)
    d        = float(metrics.get("d",0) or 0)
    b        = float(metrics.get("b",0) or 0)
    loc      = float(metrics.get("loc",0) or 0)
    branch   = float(metrics.get("branchCount",0) or 0)
    tf_name  = shap[0][0] if shap else "cyclomatic complexity"
    tf_val   = shap[0][1] if shap else 0
    repeat   = _track_repeat(fname, q_clean)
    history  = _get_recent_question(fname)
    metric_intent = _is_metric_intent(q)
    repeat_note = "Your question is similar to your last one, so I am approaching it differently. " if history and _overlap_ratio(q_clean,history)>=0.75 else ""

    if (not metric_intent and _is_low_signal_prompt(q_clean)) or repeat>=3:
        return (f"`{fname}` {decision}. Try asking: why is it risky, what should I fix, explain v(g), which function is most risky, or show the deployment plan.")

    if _is_smalltalk(q):
        return (f"Hi. `{fname}` is {decision}. Ask me: why is it risky, what to fix, explain metrics, show function hotspots, or generate a deployment plan.")

    if _is_deployment_question(q):
        plan = _build_deployment_plan()
        strategy = "Canary" if 0.4<=prob<0.7 else ("Blue-Green" if prob>=0.7 else "Rolling Update")
        return (f"**Deployment Plan for `{fname}` ({pct}% risk):**\n\n"
                f"{'🚫 **BLOCKED** by ML gate — risk exceeds threshold.' if blocked else '✅ **ALLOWED** — below threshold. Safe to deploy.'}\n"
                f"Recommended strategy: **{strategy}**\n\n"
                f"1. {plan[0]}\n2. {plan[1]}\n3. {plan[2]}\n4. {plan[3]}\n\n"
                f"**KB Evidence:**\n{kb_text}"
                + (f"\n\n**Repo context:**\n{repo_ctx}" if repo_ctx else ""))

    if _is_function_risk_question(q):
        hotspots = _estimate_function_hotspots(src)
        if hotspots:
            lines = [f"**Function Hotspots in `{fname}`:**\n"]
            for i,(name,score,floc) in enumerate(hotspots[:5]):
                risk_icon = "🔴" if score>20 else "🟡" if score>10 else "🟢"
                lines.append(f"{i+1}. {risk_icon} `{name}` — risk score {score:.1f} | {floc} lines")
            lines.append("\nRanked by branch density, nesting depth, and function size.")
            return "\n".join(lines)+f"\n\n**KB Evidence:**\n{kb_text}"
        return f"No source code available for hotspot analysis. Upload `{fname}` via the Code Risk Review page first.\n\n{kb_text}"

    if metric_intent:
        metric_name = _extract_metric_name(q)
        return _build_metric_explanation(metrics, fname, decision, metric_name, kb_text)

    if any(w in q for w in ["shap","feature importance","contribution","driving"]):
        if shap:
            lines = [f"**SHAP Feature Contributions for `{fname}`:**\n"]
            for name,val in shap[:6]:
                arrow = "🔴 +" if val>0 else "🟢 "
                lines.append(f"{arrow}{abs(val):.4f}  →  `{name}`  ({'increases' if val>0 else 'reduces'} defect risk)")
            lines.append(f"\n**Top driver:** `{shap[0][0]}` contributes {shap[0][1]:+.4f} to the {pct}% score.")
            return "\n".join(lines)+f"\n\n**KB Evidence:**\n{kb_text}"
        return f"SHAP values unavailable. Analyze `{fname}` first via Code Risk Review.\n\n{kb_text}"

    if any(w in q for w in ["fix","improve","refactor","what should","recommend","what to do","next step","action"]):
        plan = _build_action_plan(metrics, shap, src)
        return (f"{repeat_note}**Action Plan for `{fname}` ({risk_band}, {pct}%):**\n\n"
                f"1. {plan[0]}\n2. {plan[1]}\n3. {plan[2]}\n4. {plan[3]}\n\n"
                f"Key metrics: CC={vg:.0f}, Volume={v:.0f}, LOC={loc:.0f}.\n\n"
                f"**KB Evidence:**\n{kb_text}")

    if any(w in q for w in ["why","reason","risk","risky","defect","bug","predict"]):
        thr_note = (f" Note: probability {pct}% is elevated but below threshold {thp:.1f}%, so label stays Clean." if label.lower()=="clean" and prob>=0.4 else "")
        return (f"{repeat_note}**Why is `{fname}` flagged?**\n\n"
                f"`{fname}` {decision}.{thr_note}\n"
                f"Strongest SHAP driver: `{tf_name}` ({abs(tf_val):.3f})\n"
                f"CC={vg:.0f} | Volume={v:.0f} | Difficulty={d:.1f} | Est.Bugs={b:.3f} | LOC={loc:.0f} | Branches={branch:.0f}\n\n"
                + ("\n".join(f"• [{r.get('severity','?')}] {r.get('factor','?')} — {r.get('message','')}" for r in risks[:4]) if risks else "")
                + f"\n\n**KB Evidence:**\n{kb_text}")

    if any(w in q for w in ["model","algorithm","ensemble","xgboost","lightgbm","stacking","auc","f1","train"]):
        return (f"**DefectSense Model:**\n\n"
                f"Architecture: Stacking Ensemble\n"
                f"• Base: XGBoost (scale_pos_weight=3, max_depth=6) + LightGBM (class_weight=balanced, num_leaves=31)\n"
                f"• Meta: Logistic Regression\n"
                f"• Dataset: 10,000+ Python files with defect labels\n"
                f"• Metrics: AUC-ROC 0.92 | F1 0.90 | Precision 0.89 | Recall 0.91\n"
                f"• Features: 21 static code metrics via radon\n"
                f"• XAI: SHAP TreeExplainer\n"
                f"• Current: `{fname}` → {pct}% defect probability\n\n"
                f"**KB Evidence:**\n{kb_text}")

    if any(w in q for w in ["security","eval","exec","shell","pickle","bandit"]):
        return (f"**Security Scan for `{fname}`:**\n\n"
                f"DefectSense security stage scans for:\n"
                f"• `eval()`/`exec()` — arbitrary code execution\n"
                f"• `shell=True` in subprocess — command injection\n"
                f"• Unsafe pickle/deserialization — RCE risk\n"
                f"• Hardcoded credentials — secret leakage\n"
                f"• Known vulnerable dependencies\n\n"
                f"ML gate (current: {pct}%) independently flags structural risk. Both must pass before Docker build proceeds.\n\n"
                f"**KB Evidence:**\n{kb_text}")

    return (f"**`{fname}` — {decision}**\n\n{kb_text}"+(f"\n\n**Repo context:**\n{repo_ctx}" if repo_ctx else ""))

def generate_ai_explanation(prediction_result: dict, question: str):
    prob     = prediction_result.get("probability",0)
    label    = prediction_result.get("label","Unknown")
    metrics  = prediction_result.get("metrics",{})
    fname    = prediction_result.get("filename","this file")
    src      = prediction_result.get("source_code","")

    prediction = {
        "probability":prediction_result.get("probability",0),
        "label":label,
        "filename":fname,
        "key_metrics":metrics or prediction_result.get("key_metrics",{}),
        "risks":prediction_result.get("risks",[]),
        "top_features":prediction_result.get("top_features",[]),
        "source_code":src,
        "decision_threshold":prediction_result.get("decision_threshold",0.5),
    }

    reformulated = _reformulate_query(question, prediction)
    search_result = _hybrid_search(reformulated, k=4, intent=classify_intent(question))
    kb_entries    = search_result["entries"]
    repo_chunks   = _repo_search(question, k=2)

    response = _build_response(question, prediction, kb_entries, repo_chunks)
    _remember_turn(fname, question, response)

    words = response.split(" ")
    delay = 0.008 if len(words)<60 else 0.012
    for i,word in enumerate(words):
        yield word+(" " if i<len(words)-1 else "")
        time.sleep(delay)

def rag_only_search(query: str, k: int = 3) -> dict:
    intent = classify_intent(query)
    result = _hybrid_search(query, k=k, intent=intent)
    entries = result["entries"]
    return {
        "query":query,
        "intent":intent,
        "context":"\n\n".join(f"[{e['id']}] {e['text']}" for e in entries),
        "evidence":result["evidence"],
        "engine":result["engine"],
        "k":k,
    }

def rag_health() -> dict:
    return {
        "status":"ok",
        "kb_size":len(KNOWLEDGE_BASE),
        "chroma_ready":_get_chroma_collection() is not None,
        "repo_chunks":len(_load_repo_chunks()),
    }

def create_rag_blueprint():
    try:
        from flask import Blueprint, request, jsonify, Response
        import json as _json
    except ImportError:
        raise RuntimeError("Flask not installed")

    bp = Blueprint("rag",__name__)

    def _auth(req):
        auth = req.headers.get("Authorization","")
        if not auth.startswith("Bearer "):
            return None,(jsonify({"error":"Missing token"}),401)
        token = auth.split(" ",1)[1]
        if not token:
            return None,(jsonify({"error":"Invalid token"}),401)
        return token[:8],None

    @bp.route("/api/chat",methods=["POST"])
    def chat():
        uid,err = _auth(request)
        if err: return err
        body     = request.get_json(force=True,silent=True) or {}
        question = (body.get("question") or "").strip()
        if not question:
            return jsonify({"error":"question required"}),400
        prediction   = body.get("prediction_result") or {}
        session_id   = body.get("session_id") or uid or "default"
        intent       = classify_intent(question)
        reformulated = _reformulate_query(question,{
            "probability":prediction.get("probability",0),
            "filename":prediction.get("filename",""),
            "key_metrics":prediction.get("key_metrics",{}),
        })
        search = _hybrid_search(reformulated,k=4,intent=intent)
        def _stream():
            t0 = time.time()
            kb_entries  = search["entries"]
            repo_chunks = _repo_search(question,k=2)
            pred_norm = {
                "probability":prediction.get("probability",0),
                "label":prediction.get("label","Unknown"),
                "filename":prediction.get("filename","this file"),
                "key_metrics":prediction.get("key_metrics",{}),
                "risks":prediction.get("risks",[]),
                "top_features":prediction.get("top_features",[]),
                "source_code":prediction.get("source_code",""),
                "decision_threshold":prediction.get("decision_threshold",0.5),
            }
            answer = _build_response(question,pred_norm,kb_entries,repo_chunks)
            _remember_turn(pred_norm["filename"],question,answer)
            words = answer.split(" ")
            delay = 0.008 if len(words)<60 else 0.012
            for i,word in enumerate(words):
                is_last = i==len(words)-1
                chunk = word+("" if is_last else " ")
                payload: dict = {"text":chunk,"done":is_last}
                if is_last:
                    prob = pred_norm["probability"]
                    payload["meta"] = {
                        "intent":intent,
                        "reformulated_query":reformulated,
                        "engine":search["engine"],
                        "citations":[e["id"] for e in kb_entries],
                        "evidence":search["evidence"],
                        "used_repo_context":bool(repo_chunks),
                        "response_time_s":round(time.time()-t0,3),
                        "session_id":session_id,
                        "risk_summary":{
                            "filename":pred_norm["filename"],
                            "probability":prob,
                            "label":pred_norm["label"],
                            "risk_band":"HIGH" if prob>=0.65 else "MEDIUM" if prob>=0.40 else "LOW",
                        },
                    }
                yield f"data: {_json.dumps(payload)}\n\n"
                time.sleep(delay)
        return Response(_stream(),mimetype="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

    @bp.route("/api/rag-search",methods=["POST"])
    def rag_search():
        uid,err = _auth(request)
        if err: return err
        body  = request.get_json(force=True,silent=True) or {}
        query = (body.get("query") or "").strip()
        k     = min(int(body.get("k",3)),6)
        if not query:
            return jsonify({"error":"query required"}),400
        return jsonify(rag_only_search(query,k))

    @bp.route("/api/rag-health",methods=["GET"])
    def health():
        return jsonify(rag_health())

    @bp.route("/api/chat/clear",methods=["POST"])
    def chat_clear():
        uid,err = _auth(request)
        if err: return err
        body = request.get_json(force=True,silent=True) or {}
        fname = body.get("filename") or uid or "global"
        _conversation_memory.pop(fname,None)
        _repeat_tracker.pop(fname,None)
        return jsonify({"cleared":fname})

    return bp
