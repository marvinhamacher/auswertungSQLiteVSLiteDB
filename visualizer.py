#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from hardwareService import get_cpu_display_name

DB_LABELS = {'sqlite':'SQLite','litedb':'LiteDB'}
DBS = ['sqlite','litedb']
OPS = ['insert','select','update','transaction','delete']
METRICS = {
    'exec_time':'Ausführungszeit','tps':'TPS','queryrate':'Query Rate',
    'latency_avg':'Latenz Ø','latency_min':'Latenz min','latency_max':'Latenz max'
}
CATEGORIES = {'lowend':'Low-End','midrange':'Mid-Range','highend':'High-End','unknown':'Unbekannt'}

# CPU identification is handled centrally by hardwareService.py.
# The Windows processor string alone is not unique enough; the service uses
# processor + cores + threads + observed maximum frequency.
# Optional manually verified category overrides.
CUSTOM_CPU_CATEGORY_MAP = {}


def num(v, default=math.nan):
    try: return float(v)
    except (TypeError, ValueError): return default


def score_hardware(hw):
    c=hw.get('cpu',{}); r=hw.get('ram',{})
    return (num(c.get('cores'),0)*30 + num(c.get('threads'),0)*15 +
            num((c.get('frequency_mhz') or {}).get('max'),0)/100*5 +
            num(r.get('size_gb'),0)*2 + num(r.get('frequency_mhz'),0)/1000*10)


def category(hw):
    raw=hw.get('cpu',{}).get('processor','')
    if raw in CUSTOM_CPU_CATEGORY_MAP: return CUSTOM_CPU_CATEGORY_MAP[raw]
    s=score_hardware(hw)
    if s <= 349: return 'lowend'
    if s <= 649: return 'midrange'
    return 'highend'


def cpu_name(hw):
    return get_cpu_display_name(hw)


def test_code(data):
    keys=['test_code','testCode','test_id','testId','testkürzel','testkuerzel','code']
    for k in keys:
        if data.get(k) not in (None,''): return str(data[k])
    meta=data.get('metadata',{})
    if isinstance(meta,dict):
        for k in keys:
            if meta.get(k) not in (None,''): return str(meta[k])
    return ''


def load(path):
    path=Path(path)
    with path.open(encoding='utf-8') as f: d=json.load(f)
    if not isinstance(d.get('results'),list): raise ValueError("'results' muss eine Liste sein")
    return {'path':path,'hardware':d.get('hardware',{}),'results':d['results'],
            'category':category(d.get('hardware',{})),'test_code':test_code(d)}


def iteration(ds,n):
    for r in ds['results']:
        try:
            if int(r.get('iteration'))==n: return r
        except (TypeError,ValueError): pass
    return None


def value(ds,it,metric,db,thread,op):
    r=iteration(ds,it)
    if not r: return math.nan
    if metric=='exec_time': return num((r.get('exec_time') or {}).get(db))
    d=(r.get('results') or {}).get(db) or {}
    if metric=='tps': return num(((d.get('tps') or {}).get(str(thread)) or {}).get('successful_transactions_per_second'))
    if metric=='queryrate': return num(((d.get('queryrate') or {}).get(str(thread)) or {}).get(op))
    ld=((d.get('latency') or {}).get(str(thread)) or {}).get(op) or {}
    return num(ld.get(metric.removeprefix('latency_')+'_ms'))


def label(ds, mode, idx):
    hw=ds['hardware']; c=hw.get('cpu',{}); r=hw.get('ram',{})
    ram=num(r.get('size_gb'))
    hardware=f"{cpu_name(hw)} · {c.get('cores','?')}C/{c.get('threads','?')}T · {ram:.1f} GB" if not math.isnan(ram) else f"{cpu_name(hw)} · {c.get('cores','?')}C/{c.get('threads','?')}T"
    if mode=='anonym': return hardware
    if mode=='competition': return hardware if ds.get('is_competitor') else f'Teilnehmer {idx+1}'
    return hardware + (f"\n{ds['test_code']}" if ds.get('test_code') else '')


def draw(ax, datasets, metric, db_mode, thread, op, mode, competitor, groups):
    ax.clear()
    if not datasets:
        ax.text(.5,.5,'Keine Benchmarks geladen',ha='center',va='center'); ax.set_axis_off(); return
    ds=list(datasets)
    rank={'highend':0,'midrange':1,'lowend':2,'unknown':3}
    if groups: ds.sort(key=lambda x:(rank.get(x['category'],9), label(x,'normal',0).lower()))
    comp=(competitor or '').strip().lower()
    for x in ds: x['is_competitor']=bool(comp and x.get('test_code','').lower()==comp)
    dbs=DBS if db_mode=='both' else [db_mode]
    ndb=len(dbs); bw=.14 if ndb==1 else .075
    group_w=5*ndb*bw; gap=bw*3
    centers=[]
    for i,d in enumerate(ds):
        center=i*(group_w+gap); centers.append(center)
        start=center-group_w/2
        for it in range(1,6):
            for j,db in enumerate(dbs):
                x=start+((it-1)*ndb+j+.5)*bw
                v=value(d,it,metric,thread,op) if False else value(d,it,metric,db,thread,op)
                b=ax.bar(x, 0 if math.isnan(v) else v, width=bw*.9, label=DB_LABELS[db] if i==0 else None)
                if d['is_competitor']: b[0].set_hatch('//')
                if math.isnan(v): b[0].set_alpha(.15)
    ax.set_xticks(centers); ax.set_xticklabels([label(d,mode,i) for i,d in enumerate(ds)],rotation=18,ha='right')
    for center in centers:
        for it in range(1,6):
            off=((it-.5)*ndb)*bw
            ax.text(center-group_w/2+off, -.045, str(it), transform=ax.get_xaxis_transform(), ha='center', va='top', fontsize=9)
    if groups:
        last=None
        for i,d in enumerate(ds):
            if d['category']!=last:
                if i: ax.axvline((centers[i-1]+centers[i])/2,ls='--',lw=.8,alpha=.5)
                last=d['category']
    unit='ms' if metric.startswith('latency_') or metric=='exec_time' else ('Transaktionen/s' if metric=='tps' else 'Operationen/s')
    title=METRICS[metric]
    if metric!='exec_time': title+=f' · {op.upper()} · {thread} Threads' if metric!='tps' else f' · {thread} Threads'
    ax.set_title(title); ax.set_ylabel(f'{METRICS[metric]} [{unit}]'); ax.grid(axis='y',alpha=.25); ax.set_axisbelow(True); ax.legend()
    ax.figure.subplots_adjust(bottom=.30,left=.09,right=.98,top=.90)


class App:
    def __init__(self,root,files=(),mode='anonym',competitor='',groups=True):
        self.root=root; root.title('SQLite vs. LiteDB – Benchmark Visualizer'); root.geometry('1450x900'); self.ds=[]
        self.metric=tk.StringVar(value='queryrate'); self.db=tk.StringVar(value='sqlite'); self.thread=tk.StringVar(value='1'); self.op=tk.StringVar(value='select'); self.mode=tk.StringVar(value=mode); self.comp=tk.StringVar(value=competitor); self.groups=tk.BooleanVar(value=groups)
        f=ttk.Frame(root,padding=8); f.pack(fill='x')
        ttk.Button(f,text='JSON laden',command=self.select).grid(row=0,column=0,padx=4); ttk.Button(f,text='Alles löschen',command=self.clear).grid(row=0,column=1,padx=4)
        for col,text,var,vals in [(2,'Metrik',self.metric,list(METRICS)),(4,'DB',self.db,['sqlite','litedb','both']),(6,'Threads',self.thread,['1','2','4','8','16']),(8,'Operation',self.op,OPS)]:
            ttk.Label(f,text=text+':').grid(row=0,column=col,padx=(18,3)); ttk.Combobox(f,textvariable=var,values=vals,state='readonly',width=14).grid(row=0,column=col+1)
        ttk.Label(f,text='Modus:').grid(row=1,column=0); ttk.Combobox(f,textvariable=self.mode,values=['anonym','competition','normal'],state='readonly',width=14).grid(row=1,column=1)
        ttk.Label(f,text='Konkurrenz-Code:').grid(row=1,column=2,padx=(18,3)); ttk.Entry(f,textvariable=self.comp,width=20).grid(row=1,column=3)
        ttk.Checkbutton(f,text='Specification-Gruppen',variable=self.groups).grid(row=1,column=4,columnspan=2,sticky='w',padx=18)
        left=ttk.Frame(root,padding=8); left.pack(side='left',fill='y'); ttk.Label(left,text='Geladene Benchmarks').pack(anchor='w')
        self.tree=ttk.Treeview(left,columns=('category','cpu','test'),show='headings',height=28); [self.tree.heading(c,text=t) for c,t in [('category','Kategorie'),('cpu','CPU'),('test','Test')]]; self.tree.column('category',width=95); self.tree.column('cpu',width=250); self.tree.column('test',width=100); self.tree.pack(fill='y',expand=True)
        right=ttk.Frame(root,padding=8); right.pack(side='right',fill='both',expand=True); self.fig,self.ax=plt.subplots(figsize=(12,7)); self.canvas=FigureCanvasTkAgg(self.fig,master=right); self.canvas.get_tk_widget().pack(fill='both',expand=True)
        for v in [self.metric,self.db,self.thread,self.op,self.mode,self.comp,self.groups]: v.trace_add('write',lambda *_: self.draw())
        self.load(files)
    def select(self):
        p=filedialog.askopenfilenames(filetypes=[('JSON','*.json'),('Alle','*.*')]); self.load(p)
    def load(self,paths):
        errs=[]
        for p in paths:
            try:self.ds.append(load(p))
            except Exception as e:errs.append(f'{Path(p).name}: {e}')
        self.tree.delete(*self.tree.get_children())
        for d in self.ds:self.tree.insert('','end',values=(CATEGORIES[d['category']],cpu_name(d['hardware']),d['test_code'] or '—'))
        self.draw()
        if errs:messagebox.showerror('Fehler', '\n'.join(errs))
    def clear(self):self.ds.clear(); self.tree.delete(*self.tree.get_children()); self.draw()
    def draw(self):draw(self.ax,self.ds,self.metric.get(),self.db.get(),int(self.thread.get()),self.op.get(),self.mode.get(),self.comp.get(),self.groups.get()); self.canvas.draw_idle()


def boolean(v):
    v=v.lower();
    if v in ('true','1','yes','ja','on'):return True
    if v in ('false','0','no','nein','off'):return False
    raise argparse.ArgumentTypeError('true/false erwartet')


def main():
    p=argparse.ArgumentParser(); p.add_argument('files',nargs='*'); p.add_argument('--type',choices=['anonym','competition','normal'],default='anonym'); p.add_argument('--competitor',default=''); p.add_argument('--enableSpecificationGroups',type=boolean,default=True); p.add_argument('--metric',choices=list(METRICS),default='queryrate'); p.add_argument('--db',choices=['sqlite','litedb','both'],default='sqlite'); p.add_argument('--threads',type=int,choices=[1,2,4,8,16],default=1); p.add_argument('--operation',choices=OPS,default='select'); a=p.parse_args()
    root=tk.Tk(); app=App(root,a.files,a.type,a.competitor,a.enableSpecificationGroups); app.metric.set(a.metric); app.db.set(a.db); app.thread.set(str(a.threads)); app.op.set(a.operation); root.mainloop()
if __name__=='__main__':main()
