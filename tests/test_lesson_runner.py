import json
from pathlib import Path
from click.testing import CliRunner

from shaprai.cli import main
from shaprai.sanctuary.lesson_runner import LessonRunner, cosine_similarity


def write_template(path: Path):
    path.write_text('''
name: sanctuary_agent
personality:
  voice: "principled, direct, calm"
values: "honesty, integrity, compassion"
behavioral_boundaries:
  - honesty
  - integrity
  - non-manipulation
''')


def test_cosine_similarity_basic():
    assert cosine_similarity('honesty integrity', 'honesty integrity') > 0.99
    assert cosine_similarity('honesty', 'manipulation') == 0.0


def test_lesson_runner_outputs_json_like_structure(tmp_path):
    tpl = tmp_path / 'agent.yaml'
    write_template(tpl)
    runner = LessonRunner(threshold=60)
    report = runner.run(tpl, lessons='all')
    assert report['scenario_count'] >= 10
    assert 'results' in report
    assert set(report['results'][0]['scores'].keys()) == {'identity_coherence', 'anti_sycophancy', 'ethical_reasoning'}


def test_scores_are_bounded(tmp_path):
    tpl = tmp_path / 'agent.yaml'
    write_template(tpl)
    runner = LessonRunner()
    report = runner.run(tpl)
    for item in report['results']:
        for value in item['scores'].values():
            assert 0 <= value <= 100


def test_cli_sanctuary_run(tmp_path):
    tpl = tmp_path / 'agent.yaml'
    write_template(tpl)
    runner = CliRunner()
    result = runner.invoke(main, ['--skip-checks', 'sanctuary', 'run', '--agent', str(tpl), '--lessons', 'all'])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed['scenario_count'] >= 10
