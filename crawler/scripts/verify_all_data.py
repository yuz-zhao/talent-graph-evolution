"""
验证脚本：全量数据质量报告
检查所有数据文件的字段完整率，输出对比报告
"""
import csv
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

def check_csv(filepath):
    """检查 CSV 字段完整率"""
    if not os.path.exists(filepath):
        return {'status': 'MISSING'}

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    total = len(rows)
    field_stats = {}
    for col in fieldnames:
        filled = sum(1 for r in rows if r.get(col, '').strip() and r[col].strip() not in ('未注明', '', 'nan', 'None', '[]'))
        field_stats[col] = {'filled': filled, 'total': total, 'pct': round(filled * 100 / total) if total > 0 else 0}

    return {
        'status': 'OK',
        'total': total,
        'fields': field_stats,
        'sample': rows[0] if rows else None,
    }

def check_jsonl(filepath):
    """检查 JSONL 字段完整率"""
    if not os.path.exists(filepath):
        return {'status': 'MISSING'}

    items = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    total = len(items)
    if total == 0:
        return {'status': 'EMPTY', 'total': 0}

    # 统计所有 key
    all_keys = set()
    for obj in items:
        all_keys.update(obj.keys())

    field_stats = {}
    for key in sorted(all_keys):
        filled = sum(1 for obj in items if obj.get(key) is not None and obj.get(key) != '' and obj.get(key) != [])
        field_stats[key] = {'filled': filled, 'total': total, 'pct': round(filled * 100 / total)}

    return {
        'status': 'OK',
        'total': total,
        'fields': field_stats,
        'sample_keys': sorted(all_keys),
    }

def check_json(filepath):
    """检查 JSON 文件"""
    if not os.path.exists(filepath):
        return {'status': 'MISSING'}

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, list):
        total = len(data)
        return {'status': 'OK', 'total': total, 'type': 'list'}
    elif isinstance(data, dict):
        return {'status': 'OK', 'total': len(data), 'type': 'dict', 'keys': list(data.keys())[:5]}
    else:
        return {'status': 'OK', 'total': 1, 'type': type(data).__name__}

def main():
    print('=' * 70)
    print('  爬虫数据质量验证报告')
    print('=' * 70)

    all_good = True
    issues = []

    # CSV 文件检查
    csv_files = {
        'jd_clean.csv': 'clean/jd_clean.csv',
        'profiles_github_public.csv': 'clean/profiles_github_public.csv',
        'resumes_synthetic_demo.csv': 'clean/resumes_synthetic_demo.csv',
        'resumes_anonymized_evaluation.jsonl': 'clean/resumes_anonymized_evaluation.jsonl',
        'jd_raw.csv': 'raw/jd_raw.csv',
        'skill_candidates.csv': 'clean/skill_candidates.csv',
        'course_data.csv': 'education/course_data.csv',
        'certificate_data.csv': 'education/certificate_data.csv',
        'job_standard_dict.csv': 'meta/job_standard_dict.csv',
        'gold_jd_review.csv': 'review/gold_jd_review.csv',
        'gold_resume_review.csv': 'review/gold_resume_review.csv',
        'match_label_review.csv': 'review/match_label_review.csv',
        'negative_samples_review.csv': 'review/negative_samples_review.csv',
    }

    for name, path in csv_files.items():
        fp = os.path.join(DATA_DIR, path)
        result = check_csv(fp)
        print(f'\n[{name}]')

        if result['status'] == 'MISSING':
            print(f'  MISSING')
            all_good = False
            issues.append(f'{name}: 文件不存在')
            continue

        total = result['total']
        print(f'  记录数: {total}')
        problem_fields = []
        for col, stat in result['fields'].items():
            icon = '[OK]' if stat['pct'] >= 90 else ('[WARN]' if stat['pct'] >= 50 else '[LOW]')
            print(f'  {icon} {col}: {stat["filled"]}/{total} ({stat["pct"]}%)')
            if stat['pct'] < 50:
                problem_fields.append(col)
                all_good = False
                issues.append(f'{name}.{col}: {stat["pct"]}%')

        if problem_fields:
            print(f'  PROBLEM FIELDS: {", ".join(problem_fields)}')

    # JSONL 文件检查
    jsonl_files = {
        'resume_raw.jsonl': 'raw/resume_raw.jsonl',
        'github_trend.jsonl': 'raw/github_trend.jsonl',
        'github_detail.jsonl': 'raw/github_detail.jsonl',
        'arxiv_trend.jsonl': 'raw/arxiv_trend.jsonl',
        'blog_trend.jsonl': 'raw/blog_trend.jsonl',
    }

    for name, path in jsonl_files.items():
        fp = os.path.join(DATA_DIR, path)
        result = check_jsonl(fp)
        print(f'\n[{name}]')

        if result['status'] == 'MISSING':
            print(f'  MISSING')
            all_good = False
            issues.append(f'{name}: 文件不存在')
            continue
        if result['status'] == 'EMPTY':
            print(f'  EMPTY FILE')
            continue

        total = result['total']
        print(f'  记录数: {total}')
        for col, stat in result['fields'].items():
            icon = '[OK]' if stat['pct'] >= 90 else ('[WARN]' if stat['pct'] >= 50 else '[LOW]')
            print(f'  {icon} {col}: {stat["filled"]}/{total} ({stat["pct"]}%)')
            if stat['pct'] < 50:
                all_good = False
                issues.append(f'{name}.{col}: {stat["pct"]}%')

    # JSON 文件
    json_files = {
        'skill_ontology.json': 'meta/skill_ontology.json',
        'talent_profile.json': 'meta/talent_profile.json',
        'gold_jd_set_reviewed.json': 'meta/gold_jd_set_reviewed.json',
        'gold_resume_set_reviewed.json': 'meta/gold_resume_set_reviewed.json',
        'match_label_set_reviewed.json': 'meta/match_label_set_reviewed.json',
        'negative_samples_reviewed.json': 'meta/negative_samples_reviewed.json',
    }

    for name, path in json_files.items():
        fp = os.path.join(DATA_DIR, path)
        result = check_json(fp)
        print(f'\n[{name}]')

        if result['status'] == 'MISSING':
            print(f'  MISSING')
            all_good = False
            issues.append(f'{name}: 文件不存在')
            continue

        print(f'  记录数: {result["total"]} ({result["type"]})')
        if 'keys' in result:
            print(f'  Keys: {result["keys"]}')

    # 汇总
    print(f'\n{"=" * 70}')
    if all_good:
        print('OK: All data files pass field completeness check (>=50%)')
    else:
        print(f'WARNING: {len(issues)} issues found:')
        for issue in issues:
            print(f'  - {issue}')

    print('=' * 70)

    # 特别检查：核心字段
    print('\n=== Core Checks:')

    # 1. JD 行业
    jd_path = os.path.join(DATA_DIR, 'clean', 'jd_clean.csv')
    if os.path.exists(jd_path):
        with open(jd_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            jd_rows = list(reader)
        ind_filled = sum(1 for r in jd_rows if r.get('industry', '').strip() and r['industry'] != '未注明')
        pub_filled = sum(1 for r in jd_rows if r.get('publish_time', '').strip() and r['publish_time'] != '未注明')
        print(f'  JD industry 填充率: {ind_filled}/{len(jd_rows)} ({ind_filled*100//len(jd_rows)}%)')
        print(f'  JD publish_time 填充率: {pub_filled}/{len(jd_rows)} ({pub_filled*100//len(jd_rows)}%)')

    # 2. 简历完整度
    resume_path = os.path.join(DATA_DIR, 'clean', 'resumes_synthetic_demo.csv')
    if os.path.exists(resume_path):
        with open(resume_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            resume_rows = list(reader)
        edu_filled = sum(1 for r in resume_rows if r.get('school', '').strip())
        print(f'  简历总数: {len(resume_rows)}')
        print(f'  简历 school 填充率: {edu_filled}/{len(resume_rows)} ({edu_filled*100//len(resume_rows)}%)')

    # 3. 技能层级
    skill_path = os.path.join(DATA_DIR, 'meta', 'skill_ontology.json')
    if os.path.exists(skill_path):
        with open(skill_path, 'r', encoding='utf-8') as f:
            skills = json.load(f)
        parent_count = sum(1 for v in skills.values() if v.get('parent_skill', ''))
        print(f'  技能本体总数: {len(skills)}')
        print(f'  技能 parent_skill 覆盖: {parent_count}/{len(skills)} ({parent_count*100//len(skills)}%)')

    print(f'\n{"=" * 70}')
    print('验证完成!')

if __name__ == '__main__':
    main()
