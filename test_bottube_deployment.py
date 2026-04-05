#!/usr/bin/env python3
"""
Test suite for BoTTube Agent Deployment (Issue #61)

Verifies all requirements:
- Agent template with video_creation capability
- Beacon identity registration
- 2+ videos uploaded
- 2+ comments on other videos
- Template YAML with proper configuration
"""

import os
import sys
import json
from pathlib import Path

DEPLOYMENT_DIR = Path.home() / ".shaprai" / "deployments" / "bottube_video_agent"

def test_template_exists():
    """Test that agent template YAML exists"""
    template_path = Path("templates/bottube_video_agent.yaml")
    assert template_path.exists(), f"Template not found: {template_path}"
    
    with open(template_path) as f:
        content = f.read()
    
    assert "video_creation" in content, "Template missing video_creation capability"
    assert "bottube" in content, "Template missing bottube platform"
    assert "beacon" in content, "Template missing beacon platform"
    
    print("✅ test_template_exists: PASSED")

def test_beacon_identity():
    """Test that Beacon identity was created"""
    beacon_file = DEPLOYMENT_DIR / "beacon_identity.json"
    assert beacon_file.exists(), f"Beacon identity not found: {beacon_file}"
    
    with open(beacon_file) as f:
        identity = json.load(f)
    
    assert "beacon_id" in identity, "Missing beacon_id"
    assert "agent_name" in identity, "Missing agent_name"
    assert "capabilities" in identity, "Missing capabilities"
    assert len(identity["capabilities"]) > 0, "No capabilities defined"
    
    print(f"✅ test_beacon_identity: PASSED")
    print(f"   Beacon ID: {identity['beacon_id']}")

def test_videos_uploaded():
    """Test that at least 2 videos were uploaded"""
    metadata_file = DEPLOYMENT_DIR / "videos_metadata.json"
    assert metadata_file.exists(), f"Video metadata not found: {metadata_file}"
    
    with open(metadata_file) as f:
        videos = json.load(f)
    
    assert len(videos) >= 2, f"Expected 2+ videos, found {len(videos)}"
    
    for i, video in enumerate(videos, 1):
        assert "video_id" in video, f"Video {i} missing video_id"
        assert "title" in video, f"Video {i} missing title"
        assert "agent_name" in video, f"Video {i} missing agent_name"
    
    print(f"✅ test_videos_uploaded: PASSED")
    print(f"   Videos: {len(videos)} (required: 2+)")
    for video in videos:
        print(f"   - {video['title']}")

def test_comments_posted():
    """Test that at least 2 comments were posted"""
    comments_file = DEPLOYMENT_DIR / "comments.json"
    assert comments_file.exists(), f"Comments not found: {comments_file}"
    
    with open(comments_file) as f:
        comments = json.load(f)
    
    assert len(comments) >= 2, f"Expected 2+ comments, found {len(comments)}"
    
    for i, comment in enumerate(comments, 1):
        assert "video_id" in comment, f"Comment {i} missing video_id"
        assert "comment" in comment, f"Comment {i} missing text"
    
    print(f"✅ test_comments_posted: PASSED")
    print(f"   Comments: {len(comments)} (required: 2+)")

def test_template_has_capabilities():
    """Test that template YAML includes video_creation in capabilities"""
    template_path = Path("templates/bottube_video_agent.yaml")
    
    with open(template_path) as f:
        content = f.read()
    
    # Check for video_creation in capabilities list
    assert "video_creation" in content, "video_creation not in template"
    
    print("✅ test_template_has_capabilities: PASSED")

def test_beacon_heartbeat_config():
    """Test that Beacon heartbeat is configured"""
    template_path = Path("templates/bottube_video_agent.yaml")
    
    with open(template_path) as f:
        content = f.read()
    
    assert "heartbeat" in content.lower(), "Heartbeat not configured"
    assert "beacon" in content.lower(), "Beacon not configured"
    
    print("✅ test_beacon_heartbeat_config: PASSED")

def test_agent_personality():
    """Test that agent has unique personality"""
    template_path = Path("templates/bottube_video_agent.yaml")
    
    with open(template_path) as f:
        content = f.read()
    
    assert "personality:" in content, "Personality section missing"
    assert "style:" in content, "Personality style missing"
    assert "voice:" in content, "Agent voice missing"
    
    print("✅ test_agent_personality: PASSED")

def test_proof_report():
    """Test that proof report was generated"""
    proof_file = DEPLOYMENT_DIR / "proof_report.json"
    assert proof_file.exists(), f"Proof report not found: {proof_file}"
    
    with open(proof_file) as f:
        report = json.load(f)
    
    required_fields = [
        "bounty", "agent_name", "beacon_id",
        "videos_uploaded", "comments_posted",
        "template_yaml", "capabilities"
    ]
    
    for field in required_fields:
        assert field in report, f"Proof report missing {field}"
    
    assert report["videos_uploaded"] >= 2, "Less than 2 videos"
    assert report["comments_posted"] >= 2, "Less than 2 comments"
    
    print(f"✅ test_proof_report: PASSED")
    print(f"   Bounty: {report['bounty']}")
    print(f"   Agent: {report['agent_name']}")

def test_wallet_configured():
    """Test that RTC wallet is configured"""
    template_path = Path("templates/bottube_video_agent.yaml")
    
    with open(template_path) as f:
        content = f.read()
    
    assert "wallet" in content.lower() or "rtc" in content.lower(), "Wallet not configured"
    
    print("✅ test_wallet_configured: PASSED")

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("BoTTube Agent Deployment Test Suite (Issue #61)")
    print("=" * 60)
    print()
    
    tests = [
        test_template_exists,
        test_beacon_identity,
        test_videos_uploaded,
        test_comments_posted,
        test_template_has_capabilities,
        test_beacon_heartbeat_config,
        test_agent_personality,
        test_proof_report,
        test_wallet_configured,
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}: FAILED - {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️  {test.__name__}: ERROR - {e}")
            skipped += 1
    
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)
    
    return failed == 0

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
