"""Evidence-bearing job-title normalization with level, direction and scene separation."""
from __future__ import annotations
import csv,json,re
from dataclasses import dataclass,asdict
try:
    from ..config.settings import JOB_STANDARD_DICT
except ImportError:
    from config.settings import JOB_STANDARD_DICT

LEVEL_RULES=[('实习',['实习','intern','internship']),('初级',['初级','助理','junior','校招','应届']),('专家',['专家','expert','principal','staff']),('负责人',['负责人','lead','leader','head']),('总监',['总监','director']),('资深',['资深','senior','sr.','sr ']),('高级',['高级'])]
SCENES=[('云平台',['云平台','云计算','cloud']),('通信网络',['通信','无线网络','核心网','承载网','传输系统']),('工业互联网',['工业互联网']),('智能制造',['智能制造','工厂','制造']),('物联网',['物联网','iot']),('芯片半导体',['芯片','半导体','soc','ic']),('嵌入式终端',['嵌入式','单片机','固件']),('游戏',['游戏','game']),('金融',['金融','银行','证券']),('汽车',['汽车','车载','自动驾驶']),('医疗',['医疗','医药']),('电商',['电商','商业化']),('安全风控',['安全','风控'])]
DIRECTIONS=[('5G',['5g','第五代移动通信']),('工业互联网',['工业互联网']),('物联网',['物联网','iot']),('芯片设计',['芯片设计','ic design','soc design']),('芯片验证',['芯片验证','verification engineer']),('嵌入式',['嵌入式','firmware']),('智能制造',['智能制造']),('大语言模型',['大模型','llm','large language model']),('RAG',['rag','检索增强']),('AI智能体',['智能体','ai agent','agentic']),('自然语言处理',['nlp','自然语言']),('计算机视觉',['计算机视觉','图像','视觉算法']),('机器学习',['机器学习','machine learning']),('深度学习',['深度学习','deep learning']),('Java',['java']),('Python',['python']),('Golang',['golang','go开发']),('数据工程',['大数据','数据仓库','数据开发','data engineer']),('云原生',['云原生','kubernetes','容器']),('网络安全',['网络安全','信息安全','cybersecurity'])]

# Specific domain families precede generic roles.
ROLE_RULES=[
 ('5G通信工程师','通信与5G',['5g','第五代移动通信']),('通信网络工程师','通信与5G',['通信网络','网络优化','核心网','无线网络','传输系统','通信维护','网络维护','网络工程师','通信工程师','集合通信','云网']),
 ('工业互联网工程师','工业互联网',['工业互联网']),('物联网开发工程师','物联网',['物联网','iot engineer','iot developer']),
 ('芯片验证工程师','芯片与半导体',['芯片验证','verification engineer']),('芯片设计工程师','芯片与半导体',['芯片设计','ic design','soc design']),('芯片算法工程师','芯片与半导体',['芯片算法','chip ai','chip algorithm']),
 ('嵌入式开发工程师','嵌入式与硬件',['嵌入式','firmware engineer','固件工程师']),('智能制造工程师','智能制造',['智能制造','mes工程师','工业自动化']),
 ('游戏客户端开发工程师','软件研发',['游戏客户端','手游客户端','小游戏-客户端','android客户端','game client']),('游戏服务端开发工程师','软件研发',['游戏后台','游戏服务器','手游服务器','开放世界手游服务器','game server']),('游戏引擎开发工程师','软件研发',['游戏引擎','ue4客户端','unreal engine']),
 ('云存储研发工程师','云计算与运维',['云存储','对象存储','cloud storage']),('实时计算工程师','数据与大数据',['实时计算','stream processing']),('边缘计算工程师','云计算与运维',['边缘计算','edge computing']),
 ('自动驾驶算法工程师','人工智能',['自动驾驶','autonomous driving']),('多模态算法工程师','人工智能',['多模态','multimodal']),('提示词工程师','人工智能',['提示词工程师','prompt engineer']),('AIGC算法工程师','人工智能',['aigc','生成式ai']),
 ('大模型算法工程师','人工智能',['大模型算法','llm algorithm','大模型训练','大模型推理','大模型评测']),('大模型应用开发工程师','人工智能',['大模型应用','llm application','llm应用']),
 ('RAG应用工程师','人工智能',['rag','检索增强']),('AI智能体开发工程师','人工智能',['ai agent','agent工程师','agent 工程师','智能体']),('AI基础设施工程师','人工智能',['ai infra','ai计算库']),
 ('自然语言处理工程师','人工智能',['nlp','自然语言处理']),('计算机视觉工程师','人工智能',['计算机视觉','视觉算法','图像算法']),('机器学习工程师','人工智能',['机器学习','machine learning']),('深度学习工程师','人工智能',['深度学习','deep learning']),('人工智能算法工程师','人工智能',['ai算法','人工智能算法','算法工程师','algorithm engineer']),
 ('Java开发工程师','软件研发',['java']),('Python开发工程师','软件研发',['python']),('Android开发工程师','软件研发',['android developer','android开发']),('前端开发工程师','软件研发',['前端','frontend','front-end']),('全栈开发工程师','软件研发',['全栈','fullstack','full-stack','full stack']),('后端开发工程师','软件研发',['后端','后台开发','backend','back-end']),
 ('软件开发工程师','软件研发',['software engineer','software developer','软件研发','软件开发','研发工程师']),('平台研发工程师','软件研发',['platform engineer','平台研发']),
 ('数据仓库工程师','数据与大数据',['数据仓库','data warehouse']),('大数据开发工程师','数据与大数据',['大数据开发','数据开发','data engineer','analytics engineer','etl']),('数据分析师','数据与大数据',['数据分析','商业分析师','data analyst']),('数据建模工程师','数据与大数据',['data modeler','数据建模']),('数据治理工程师','数据与大数据',['数据治理']),('数据挖掘工程师','数据与大数据',['数据挖掘']),
 ('云计算工程师','云计算与运维',['云计算','cloud engineer','云平台']),('DevOps工程师','云计算与运维',['devops','sre','site reliability']),('运维工程师','云计算与运维',['运维']),
 ('安全工程师','安全',['安全工程师','安全经理','security engineer','cybersecurity']),('测试开发工程师','软件质量',['测试开发','测试工程师','qa engineer']),
 ('IT系统工程师','云计算与运维',['信息化工程师','it-administrator','system engineer']),('智能化系统工程师','智能制造',['弱电智能化','control systems engineer']),('技术支持工程师','技术服务',['技术支持','技术支撑','售前技术','客户成功','technical support']),('售前解决方案工程师','架构与解决方案',['解决方案经理','解决方案工程师','售前工程师','交付方案工程师']),
 ('解决方案架构师','架构与解决方案',['解决方案架构','solution architect']),('系统架构师','架构与解决方案',['架构师','architect']),('产品研发工程师','产品与项目',['it产品研发']),('产品经理','产品与项目',['产品经理','product manager']),('项目经理','产品与项目',['项目经理','project manager']),
 ('算法研究员','人工智能',['algorithm researcher','ai researcher','researcher','研究员']),
]

@dataclass
class JobMapping:
    raw_job_name:str; standard_job_name:str; job_family:str; job_level:str; job_direction:str; business_scene:str; confidence:float; mapping_method:str; mapping_evidence:str

def _hit(text,words): return next((w for w in words if w.casefold() in text.casefold()),'')
def _clean_title(title):
    value=re.sub(r'\b[A-Z]?J\d{4,}\b',' ',title,flags=re.I)
    value=re.sub(r'[（(](?:北京|上海|深圳|广州|杭州|南京|苏州|武汉|西安|合肥|成都|可投|六险|方向|base)[^）)]*[）)]',' ',value,flags=re.I)
    value=re.sub(r'\s+',' ',value).strip(' -_/|·')
    return value

def standardize_job_title(job_title:str)->JobMapping:
    raw=str(job_title or '').strip(); text=_clean_title(raw); lower=text.casefold(); evidence=[]
    level='未注明'
    for value,words in LEVEL_RULES:
        hit=_hit(lower,words)
        if hit: level=value;evidence.append({'dimension':'level','matched':hit});break
    direction='通用';
    for value,words in DIRECTIONS:
        hit=_hit(lower,words)
        if hit:direction=value;evidence.append({'dimension':'direction','matched':hit});break
    scene='通用场景'
    for value,words in SCENES:
        hit=_hit(lower,words)
        if hit:scene=value;evidence.append({'dimension':'scene','matched':hit});break
    standard='';family='';role_hit=''
    for std,fam,words in ROLE_RULES:
        role_hit=_hit(lower,words)
        if role_hit:standard=std;family=fam;evidence.insert(0,{'dimension':'role','matched':role_hit,'rule':std});break
    if standard:
        confidence=.96 if (role_hit.casefold()==text.casefold() or standard==text) else (.92 if direction!='通用' or scene!='通用场景' else .86)
        method='domain_role_rule_v2' if family in {'通信与5G','工业互联网','物联网','芯片与半导体','嵌入式与硬件','智能制造'} else 'role_keyword_rule_v2'
    else:
        standard=text or raw;family='待审核';confidence=.35;method='unresolved_review_required';evidence=[{'dimension':'unresolved','reason':'no_supported_role_rule'}]
    return JobMapping(raw,standard,family,level,direction,scene,confidence,method,json.dumps(evidence,ensure_ascii=False))

def standardize_job_name(job_title:str)->str: return standardize_job_title(job_title).standard_job_name
