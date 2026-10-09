from faker import Faker
from gevent.lock import BoundedSemaphore
from locust import HttpUser, task, SequentialTaskSet, TaskSet, constant_throughput
import random

fake = Faker('ru_RU')
print(fake.name_male())

# Пароль считается тяжело. Если 100 человек регистрируются сразу,
# сервер рвёт вход. Пускаем на регистрацию по одному.
auth_lock = BoundedSemaphore(1)

class WriteTests(SequentialTaskSet):
    @task
    def create_task(self):
        task_data = {
            'title': fake.sentence(nb_words=3).rstrip('.') + ' ' + fake.uuid4()[:8],
            'description': fake.paragraph(nb_sentences=2),
            'completed': False,
        }
        self.user.task_title = task_data['title']
        self.client.post('/api/tasks', json=task_data)

    @task
    def get_created_task(self):
        response = self.client.get('/api/tasks')
        self.user.task_id = None
        if response.status_code == 200:
            for item in response.json():
                if item['title'] == self.user.task_title:
                    self.user.task_id = item['id']

    @task
    def update_task(self):
        if self.user.task_id:
            task_data = {
                'title': self.user.task_title,
                'description': fake.paragraph(nb_sentences=2),
                'completed': random.choice([True, False]),
            }
            self.client.put('/api/tasks/' + str(self.user.task_id), json=task_data, name='/api/tasks/:id')
        self.interrupt()

class AdminTests(TaskSet):
    def on_start(self):
        email_name = fake.user_name()
        if not email_name.isascii():
            email_name = 'student'
        email = email_name + '.' + fake.uuid4()[:8] + '@example.com'
        password = fake.password(length=12)

        with auth_lock:
            self.client.post('/api/auth/register', json={
                'email': email,
                'password': password,
            })

            response = self.client.post('/api/auth/login', json={
                'email': email,
                'password': password,
                'rememberMe': random.choice([True, False]),
            })

        self.client.headers['Authorization'] = 'Bearer ' + response.json()['accessToken']
        self.user.task_id = None
        self.user.task_title = None

    @task(5)
    def get_tasks(self):
        self.client.get('/api/tasks')

    @task(5)
    def get_metrics(self):
        self.client.get('/metrics')

    tasks = {
        WriteTests: 1
    }

class WebsiteUser(HttpUser):
    wait_time = constant_throughput(2)

    tasks = [
        AdminTests
    ]
