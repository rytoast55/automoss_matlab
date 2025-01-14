from ...settings import SUBMISSION_UPLOAD_TEMPLATE
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from .models import Match
from ..jobs.models import Job
from ...settings import SUPPORTED_LANGUAGES, MATCH_CONTEXT
import os


@method_decorator(login_required, name='dispatch')
class Index(View):
    """ Result Index View """

    template = "results/index.html"

    def get(self, request, job_id):
        """ Get result """

        job = get_object_or_404(
            Job.objects.user_jobs(request.user), job_id=job_id)

        context = {
            'job': job,
            'matches': Match.objects.user_matches(request.user).filter(moss_result__job__job_id=job_id).order_by('-lines_matched')
        }
        return render(request, self.template, context)


@method_decorator(login_required, name='dispatch')
class ResultMatch(View):
    """ Match View """

    template = "results/match.html"

    def get(self, request, job_id, match_id):
        """ Get match """
        match = get_object_or_404(Match.objects.user_matches(
            request.user), match_id=match_id)
        job = get_object_or_404(
            Job.objects.user_jobs(request.user), job_id=job_id)

        submissions = {
            'first': match.first_submission,
            'second': match.second_submission
        }

        # Add IDs to matches to ensure matching
        match_info = {k: v for k, v in enumerate(match.line_matches, start=1)}

        blocks = {}

        match_numbers = None
        for submission_type, submission in submissions.items():

            file_path = SUBMISSION_UPLOAD_TEMPLATE.format(
                user_id=request.user.user_id,
                assignment=submission.assignment,
                file_type='files',
                semester=submission.semester,
                name=submission.file_name,
            )

            if not os.path.exists(file_path):
                continue

            with open(file_path) as fp:
                lines = fp.readlines()

            blocks[submission_type] = []
            current = 0

            sorted_info = sorted(
                match_info.items(), key=lambda item: item[-1][submission_type]['from'])
            if match_numbers is None:
                match_numbers = [x[0] for x in sorted_info]

            for match_id, match_lines in sorted_info:
                # TODO maybe return list of lines, not joined
                blocks[submission_type].append({
                    'text': ''.join(lines[current:match_lines[submission_type]['from'] - 1])
                })
                current = match_lines[submission_type]['to']
                blocks[submission_type].append({
                    'id': match_id,
                    'text': ''.join(lines[match_lines[submission_type]['from'] - 1:current])
                })

            # Get rest of file
            blocks[submission_type].append({
                'text': ''.join(lines[current:])
            })

        # Get highlighter name
        job_language = SUPPORTED_LANGUAGES[job.language][3]

        context = {
            'match': match,
            'submissions': submissions,
            'match_numbers': match_numbers,
            'blocks': blocks,
            'language': job_language,
            'job': job,
            **MATCH_CONTEXT
        }
        return render(request, self.template, context)
