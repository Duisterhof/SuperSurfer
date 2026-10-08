"""Disposable real service, Git source and contained compiler for browser workflows."""
import json
from pathlib import Path
import sys
import threading
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from test_conversations import ConversationTests
from server.app import create_server
fixture=ConversationTests();fixture.setUp()
fixture.service.codex.account=lambda:{'account':{'type':'chatgpt'},'login_required':False}
project=fixture.service.action('project.add',{'name':'paper-studio','repo':str(fixture.root/'paper'),'surfboard_template':'writing','goal':'Explain the method, compare measured evidence and produce a reproducible paper.'})
repo=Path(project['repo'])
(repo/'main.tex').write_text(r'''\documentclass[11pt]{article}
\usepackage{amsmath}
\usepackage[margin=1in]{geometry}
\title{Learning from Fewer Demonstrations}
\author{Research writing workflow}
\date{}
\begin{document}
\maketitle
\begin{abstract}
We study how representation reuse changes the cost of adapting a policy.
This document is a workflow demonstration, not a report of measured research results.
\end{abstract}
\section{Method}
Our approach separates representation learning from task-specific adaptation.
For each example, we minimize $\mathcal{L}(\theta)=\sum_i \|f_\theta(x_i)-y_i\|^2$.
\input{sections/evaluation.tex}
\newpage
\section{Reproducibility}
Every figure should identify its data, method, split, and evaluation protocol.
Claims remain provisional until supported by measurements.
\end{document}
''')
(repo/'sections').mkdir();(repo/'sections/evaluation.tex').write_text(r'''\section{Evaluation}
We compare methods under the same evaluation protocol and label held-out splits explicitly.
Training and validation curves should be overlaid by method, with units and clear legends.
''')
item=fixture.service.action('experiment.create',{'project_id':project['id'],'name':'Revise methods section','summary':'Clarify the method without changing unsupported claims.'})
server=create_server(fixture.service,port=0)
print(json.dumps({'port':server.server_port,'directory':str(fixture.service.directory),'project':project['id'],'item':item['id'],'repo':str(repo),'compiler':fixture.service.latex.capabilities()}),flush=True)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:sys.stdin.read()
finally:server.shutdown();server.server_close();fixture.tearDown()
