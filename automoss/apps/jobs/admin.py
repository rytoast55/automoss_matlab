from django.contrib import admin
from .models import Job, Submission, JobEvent

admin.site.register(Job)

class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'assignment', 'semester']
    list_filter = ['assignment', 'semester']
    

admin.site.register(Submission, SubmissionAdmin)
admin.site.register(JobEvent)
