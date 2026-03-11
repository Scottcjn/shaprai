import json
from pathlib import Path

from shaprai.training.sft_generator import SFTGenerator


def test_generate_examples_count(tmp_path):
    template = tmp_path / 'agent.yaml'
    template.write_text('''
name: demo_agent
personality:
  voice: "clear and grounded"
values: "honesty, integrity"
behavioral_boundaries:
  - honesty
  - integrity
''')
    g = SFTGenerator(seed=1)
    data = g.generate_examples(g.load_template(template), count=25)
    assert len(data) == 25


def test_chatml_output_contains_tokens(tmp_path):
    template = tmp_path / 'agent.yaml'
    template.write_text('''
name: demo_agent
personality:
  voice: "clear and grounded"
values: "honesty, integrity"
behavioral_boundaries:
  - honesty
  - integrity
''')
    g = SFTGenerator(seed=1)
    ex = g.generate_examples(g.load_template(template), count=1)[0]
    record = g.to_chatml_record(ex)
    assert '<|im_start|>system' in record['text']
    assert '<|im_end|>' in record['text']


def test_identity_weighted_sampling_bias(tmp_path):
    template = tmp_path / 'agent.yaml'
    template.write_text('''
name: demo_agent
personality:
  voice: "clear and grounded"
values: "honesty, integrity"
behavioral_boundaries:
  - honesty
  - integrity
''')
    g = SFTGenerator(seed=7)
    examples = g.generate_examples(g.load_template(template), count=300)
    counts = {}
    for ex in examples:
        counts[ex.category] = counts.get(ex.category, 0) + 1
    assert counts['identity'] > counts['helpfulness']
    assert counts['identity'] >= counts['disagreement']


def test_generate_file_jsonl(tmp_path):
    template = tmp_path / 'agent.yaml'
    output = tmp_path / 'train.jsonl'
    template.write_text('''
name: demo_agent
personality:
  voice: "clear and grounded"
values: "honesty, integrity"
behavioral_boundaries:
  - honesty
  - integrity
''')
    g = SFTGenerator(seed=1)
    out = g.generate_file(template, output, count=10)
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 10
    row = json.loads(lines[0])
    assert 'messages' in row and 'text' in row and 'weight' in row
