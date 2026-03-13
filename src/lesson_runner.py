import json

class LessonRunner:
    def __init__(self, lesson_data):
        self.lesson_data = lesson_data
        self.results = []

    def evaluate_lesson(self):
        for lesson in self.lesson_data:
            evaluation = self._evaluate_lesson(lesson)
            self.results.append(evaluation)
        return self._generate_json_result()

    def _evaluate_lesson(self, lesson):
        # Simulate lesson evaluation logic (to be replaced with real logic)
        return {
            'lesson_name': lesson.get('name', 'Unknown'),
            'score': 85,
            'feedback': 'Good progress, but needs more focus on details.'
        }

    def _generate_json_result(self):
        return json.dumps({'lessons': self.results}, indent=4)

# Example usage
if __name__ == '__main__':
    lessons = [
        {'name': 'Lesson 1', 'content': 'Introduction to Python'},
        {'name': 'Lesson 2', 'content': 'Advanced Python Topics'}
    ]

    runner = LessonRunner(lessons)
    result = runner.evaluate_lesson()
    print(result)