import unittest
from src.lesson_runner import LessonRunner

class TestLessonRunner(unittest.TestCase):
    def test_evaluate_lesson(self):
        lessons = [
            {'name': 'Lesson 1', 'content': 'Introduction to Python'},
            {'name': 'Lesson 2', 'content': 'Advanced Python Topics'}
        ]

        runner = LessonRunner(lessons)
        result = runner.evaluate_lesson()

        expected_result = '''{
    "lessons": [
        {
            "lesson_name": "Lesson 1",
            "score": 85,
            "feedback": "Good progress, but needs more focus on details."
        },
        {
            "lesson_name": "Lesson 2",
            "score": 85,
            "feedback": "Good progress, but needs more focus on details."
        }
    ]
}'''

        self.assertEqual(result, expected_result)

if __name__ == '__main__':
    unittest.main()