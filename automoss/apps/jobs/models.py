import uuid
from django.utils.timezone import now
from django.db import models
from django.contrib.auth import get_user_model

import os
import shutil
from ...settings import (
    SUBMISSION_TYPES,
    STATUSES,
    JOB_EVENT_CONTEXT,
    SUPPORTED_LANGUAGES,
    DEFAULT_MOSS_SETTINGS,
    UUID_LENGTH,
    MAX_COMMENT_LENGTH,
    SUBMISSION_UPLOAD_TEMPLATE,
)
from ...apps.utils.core import (to_choices, get_longest_key, first)


def get_default_comment():
    """ Returns default job comment """
    return f"My Job - {now().strftime('%d/%m/%y-%H:%M:%S')}"


User = get_user_model()


class JobManager(models.Manager):
    """ Custom Job manager """

    def user_jobs(self, user):
        """ Returns set of jobs belonging to user """
        return self.get_queryset().filter(user=user)


class Job(models.Model):
    """ Class to model Job Entity """

    # Custom manager
    objects = JobManager()

    # MOSS user that created the job
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Unique identifier used in routing
    job_id = models.CharField(
        primary_key=False,
        default=uuid.uuid4,
        max_length=UUID_LENGTH,
        editable=False,
        unique=True
    )

    # The name of the assignment that will be checked
    assignment = models.CharField(max_length=10)

    #The semester to filter for when filtering Matches
    semester = models.CharField(max_length=5)

    # Language choice
    language = models.CharField(
        max_length=get_longest_key(SUPPORTED_LANGUAGES),
        choices=[(language, SUPPORTED_LANGUAGES[language][0])
                 for language in SUPPORTED_LANGUAGES],
        default=first(SUPPORTED_LANGUAGES),
    )

    # Num Students
    num_students = models.PositiveIntegerField(default=0)

    # Max matches of a code segment before it is ignored
    max_until_ignored = models.PositiveIntegerField(
        default=DEFAULT_MOSS_SETTINGS['max_until_ignored'])

    # Max displayed matches
    max_displayed_matches = models.PositiveIntegerField(
        default=DEFAULT_MOSS_SETTINGS['max_displayed_matches'])

    # Comment/description attached to job
    comment = models.CharField(
        max_length=MAX_COMMENT_LENGTH, default=get_default_comment)

    # Job status
    status = models.CharField(
        max_length=get_longest_key(STATUSES),
        choices=to_choices(STATUSES),
        default=first(STATUSES),
    )
    # Date and time job was created
    creation_date = models.DateTimeField(default=now)

    # Date and time job was started
    start_date = models.DateTimeField(null=True, blank=True)

    # Date and time job was completed
    completion_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """ Model to string method """
        return f"{self.comment} ({self.assignment} for {self.semester})"


class Submission(models.Model):
    """ Class to model MOSS Report Entity """

    # MOSS user that created the job
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Semester the file is from
    semester = models.CharField(max_length=5)

    # Name of the assignment
    assignment = models.CharField(max_length=10)

    # Name of the submission
    file_name = models.CharField(max_length=64)

    file_type = models.CharField(
        max_length=get_longest_key(SUBMISSION_TYPES),
        choices=to_choices(SUBMISSION_TYPES)
    )

    def __str__(self):
        return f'{self.file_name}_{self.assignment}_{self.semester}'

    def delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

        media_path = SUBMISSION_UPLOAD_TEMPLATE.format(
            user_id=self.user.user_id,
            assignment=self.assignment,
            file_type=self.file_type,
            semester=self.semester,
            name=self.file_name,
        )

        if os.path.exists(media_path):
            shutil.rmtree(media_path)

            parent = os.path.dirname(media_path)
            if len(os.listdir(parent)) == 0:  # Delete parent dir if empty
                os.rmdir(parent)

class JobEvent(models.Model):
    """ Class to model Job events """

    # Job the event belongs to
    job = models.ForeignKey(Job, on_delete=models.CASCADE)

    # Date and time job was created
    date = models.DateTimeField(default=now)

    # Job status
    type = models.CharField(
        max_length=max(map(len, JOB_EVENT_CONTEXT.values())),
        choices=list((x, x) for x in JOB_EVENT_CONTEXT.values())
    )

    # Message attached to job event
    message = models.CharField(max_length=256)

    def __str__(self):
        return f'[{self.date.strftime("%Y-%m-%d %H:%M:%S")}] {self.message}'
