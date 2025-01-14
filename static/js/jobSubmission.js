// Document references to job submission elements
let createJobModalElement = document.getElementById("generate-report-modal");
let createJobModal = new bootstrap.Modal(createJobModalElement);
let createJobForm = document.getElementById("generate-report-form");
let jobName = document.getElementById("report-name");
let jobLanguage = document.getElementById("report-language");
let jobMaxMatchesUntilIgnored = document.getElementById("report-max-until-ignored");
let jobMaxMatchesDisplayed = document.getElementById("report-max-displayed-matches");
let jobMessage = document.getElementById("report-message");
let createJobButton = document.getElementById("generate-report-button");

let sizeExceededModalElement = document.getElementById("size-exceeded-modal");
let sizeExceededModal = new bootstrap.Modal(sizeExceededModalElement);

let timedMessage = undefined;
let isShowingTimedMessage = false;

/**
 * Set the message at the bottom left hand corner of the job submission modal. If the current message
 * being displayed is timed, it will stop and be replaced with the new one.
 */
function setMessage(message, colour){
	if (isShowingTimedMessage){
		clearInterval(timedMessage);
	}
	jobMessage.textContent = message;
	jobMessage.style.color = colour;
}

/**
 * Display a message that times out after a specified duration.
 */
function showTimedMessage(message, colour, duration, onShow, onTimeout){
	if (isShowingTimedMessage){
		clearTimeout(timedMessage);
	}

	setMessage(message, colour);
	isShowingTimedMessage = true;
	onShow();

	timedMessage = setTimeout(function () {
		setMessage("", "white");
		isShowingTimedMessage = false;
		onTimeout();
	}, 
	duration);
}

/**
 * Display an error message that shakes the modal and times out after 3 seconds.
 */
function displayError(errorMessage) {
	showTimedMessage(errorMessage, "var(--bs-danger)", 3000, function(){
		createJobModalElement.classList.add("animate__animated", "animate__shakeX");
	}, function(){
		createJobModalElement.classList.remove("animate__animated", "animate__shakeX");
	});
}

/**
 * Toggle job submission (i.e., whether you can submit jobs or not).
 */
function setEnabled(isEnabled) {
	createJobButton.disabled
		= jobName.disabled
		= jobLanguage.disabled
		= jobMaxMatchesUntilIgnored.disabled
		= jobMaxMatchesDisplayed.disabled
		= jobAttachBaseFiles.disabled
		= !isEnabled;
}

/**
 * Downloads the python script to perform pre-processing locally.
 */
function downloadPythonScript(){
	location.href = PYTHON_SCRIPT_URL;
}

createJobForm.onsubmit = async (e) => {
	e.preventDefault(); // Prevent the modal from closing immediately.
	
	try {
		// Create a new form (and capture name, language, max matches until ignored and max matches displayed)
		let jobFormData = new FormData(createJobForm);
		setEnabled(false);
		setMessage("Stitching...", "white");

		// Submit the job (must use XMLHttpRequest to receive callbacks about upload progress).
		let xhr = new XMLHttpRequest();
		xhr.responseType = 'json';
		xhr.open('POST', NEW_JOB_URL);

		// https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/upload
		// Other events: error, abort, timeout

		xhr.upload.addEventListener('loadstart', e => {
			setMessage("Uploading (0%)", "white");
		});
		xhr.upload.addEventListener('progress', e => {
			let percentage = e.lengthComputable ? (e.loaded / e.total) * 100 : 0;
			setMessage(`Uploading (${percentage.toFixed(0)}%)`, "white");
		});
		// Done uploading, now server is processing upload (writing files to disk).
		xhr.upload.addEventListener('load', e => {
			setMessage("Waiting for server...", "white");
		});
		xhr.onreadystatechange = function (){ // Call a function when the state changes.
			if (this.readyState === XMLHttpRequest.DONE){
				if (this.status === 200){

					// Hide and reset the form and dropzone.
					createJobModal.hide();
					setTimeout(() => { // Timeout to ensure that the modal only clears once closed.
						createJobForm.reset();
						updateForBaseFiles();
						setEnabled(true);
						setMessage("", "white");
					}, 200);

				}else if (this.status === 400){ // Server returns an error message regarding the submission.
					try {
						displayError(xhr.response.message);
					} catch (error) {
						displayError(error);
					}
					setEnabled(true);
				}
			}
		}
		xhr.send(jobFormData);

	}catch(err){ // Unknown client-side error.
		console.error(err);
		displayError("An error occurred.");
		setEnabled(true);
	}
};
