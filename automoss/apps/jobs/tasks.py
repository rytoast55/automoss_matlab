
import random
from ..results.models import MOSSResult, Match
from .models import Job, Submission
from django.utils.timezone import now
from django.core.files.uploadedfile import UploadedFile
from ..moss.pinger import Pinger, LoadStatus
from ..moss.moss import (
    MOSS,
    Result,
    RecoverableMossException,
    EmptyResponse,
    FatalMossException,
    is_valid_moss_url
)
from ...settings import (
    SUPPORTED_LANGUAGES,
    PROCESSING_STATUS,
    COMPLETED_STATUS,
    FAILED_STATUS,
    SUBMISSION_TYPES,
    FILES_NAME,
    JOB_UPLOAD_TEMPLATE,
    DEBUG,

    MIN_RETRY_TIME,
    MAX_RETRY_TIME,
    MAX_RETRY_DURATION,
    EXPONENTIAL_BACKOFF_BASE,
    FIRST_RETRY_INSTANT
)
from ..utils.core import retry
import os
import json
import time
from celery.decorators import task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)


def get_moss_language(language):
    return next((SUPPORTED_LANGUAGES[l][1] for l in SUPPORTED_LANGUAGES if l == language), None)


LOG_FILE = 'jobs.log'


@task(name='Upload')
def process_job(job_id):
    """Basic interface for generating a report from MOSS"""

    job = Job.objects.get(job_id=job_id)

    if job.status == COMPLETED_STATUS:
        # Do not process completed jobs
        # Necessary because redis stores a list of these jobs in the database when the server goes offline
        # Alternative: Delete dump.rdb on server start (bad idea)?
        return

    logger.info(f'Starting job {job_id} with status {job.status}')

    job.status = PROCESSING_STATUS
    job.save()

    base_dir = JOB_UPLOAD_TEMPLATE.format(job_id=job.job_id)

    paths = {}

    for file_type in SUBMISSION_TYPES:
        path = os.path.join(base_dir, file_type)
        if not os.path.isdir(path):
            continue  # Ignore if none of these files were submitted

        paths[file_type] = []
        for f in os.listdir(path):
            file_path = os.path.join(path, f)
            if os.path.getsize(file_path) > 0:
                # Only add non-empty files
                paths[file_type].append(file_path)

    if not paths.get(FILES_NAME):
        # TODO raise exception : no files supplied
        job.status = FAILED_STATUS  # TODO detect failure
        job.save()
        return None

    num_attempts = 0
    url = None
    result = None

    for attempt, time_to_sleep in retry(MIN_RETRY_TIME, MAX_RETRY_TIME, EXPONENTIAL_BACKOFF_BASE, MAX_RETRY_DURATION, FIRST_RETRY_INSTANT):
        num_attempts = attempt

        try:
            error = None
            if not is_valid_moss_url(url):
                # Keep retrying until valid url has been generated
                # Do not restart whole job if this succeeds but parsing fails
                url = MOSS.generate_url(
                    user_id=job.user.moss_id,
                    language=get_moss_language(job.language),
                    **paths,
                    max_until_ignored=job.max_until_ignored,
                    max_displayed_matches=job.max_displayed_matches,
                    use_basename=True,
                )
                logger.info(f'Generated url: "{url}"')

            # TODO set status to parsing?

            logger.info('Start parsing report')
            # Parsing and extraction
            result = MOSS.generate_report(url)
            logger.info(
                f'Result finished parsing: {len(result.matches)} matches detected.')

            break  # Success, do not retry

        except RecoverableMossException as e:
            error = e  # Handled below

        except EmptyResponse as e:
            # Job ended after
            error = e

            load_status = Pinger.determine_load()
            if load_status == LoadStatus.NORMAL:
                logger.debug(
                    f'Moss is not under load - job ({job_id}) will never finish')
                break

            elif load_status == LoadStatus.UNDER_LOAD:
                logger.debug(f'Moss is under load, retrying job ({job_id})')
            else:
                logger.debug(f'Moss is down, retrying job ({job_id})')

        except FatalMossException as e:
            break  # Will be handled below (result is None)

        except Exception as e:
            # TODO something catastrophic happened
            # Do some logging here
            logger.error(f'Unknown error: {e}')
            break  # Will be handled below (result is None)

        # We can retry
        logger.warning(
            f'(Attempt {attempt}) Error: {error} | Retrying in {time_to_sleep} seconds')
        time.sleep(time_to_sleep)

    # Represents when no more processing of the job will occur
    job.completion_date = now()

    failed = result is None
    job.status = FAILED_STATUS if failed else COMPLETED_STATUS  # TODO detect failure
    job.save()

    if DEBUG:
        # Calculate average file_size
        num_files = len(paths[FILES_NAME])
        avg_file_size = sum([os.path.getsize(x)
                            for x in paths[FILES_NAME]])/num_files

        log_info = vars(job).copy()
        log_info.pop('_state', None)
        log_info.update({
            'num_files': num_files,
            'avg_file_size': avg_file_size,
            'moss_id': job.user.moss_id,
            'num_attempts': num_attempts
        })

        log_info.update(Pinger.ping() or {})
        logger.debug(f'Job info: {log_info}')

        with open(LOG_FILE, 'a+') as fp:
            log_info['duration'] = (
                log_info['completion_date'] - log_info['start_date']).total_seconds()
            json.dump(log_info, fp, sort_keys=True, default=str)
            print(file=fp)

    if failed:
        return None

    moss_result = MOSSResult.objects.create(
        job=job,
        url=result.url
    )

    for match in result.matches:
        Match.objects.create(
            moss_result=moss_result,
            first_submission=Submission.objects.get(
                job=job, submission_id=match.name_1),
            second_submission=Submission.objects.get(
                job=job, submission_id=match.name_2),
            first_percentage=match.percentage_1,
            second_percentage=match.percentage_2,
            lines_matched=match.lines_matched,
            line_matches=match.line_matches
        )

    return result.url
