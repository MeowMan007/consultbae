// ConsultBae Audio Studio - Minimal Monochrome Theme Logic

document.addEventListener("DOMContentLoaded", () => {
    // State variables
    let mediaRecorder = null;
    let audioChunks = [];
    let recordedBlob = null;
    let selectedFile = null;
    let audioStream = null;
    let audioCtx = null;
    let analyser = null;
    let animationId = null;
    let timerInterval = null;
    let recordingStartTime = 0;

    // DOM Elements
    const btnTabSubmit = document.getElementById("btn-tab-submit");
    const btnTabGallery = document.getElementById("btn-tab-gallery");
    const tabSubmit = document.getElementById("tab-submit");
    const tabGallery = document.getElementById("tab-gallery");

    const toggleRecord = document.getElementById("toggle-record");
    const toggleUpload = document.getElementById("toggle-upload");
    const recorderBox = document.getElementById("recorder-box");
    const uploadBox = document.getElementById("upload-box");

    const btnStartRecord = document.getElementById("btn-start-record");
    const btnStopRecord = document.getElementById("btn-stop-record");
    const recTimer = document.getElementById("rec-timer");
    const canvas = document.getElementById("waveform-canvas");
    const canvasCtx = canvas.getContext("2d");

    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const previewBox = document.getElementById("preview-box");
    const previewPlayer = document.getElementById("preview-player");
    const btnClearAudio = document.getElementById("btn-clear-audio");
    const btnSubmit = document.getElementById("btn-submit");

    const workerName = document.getElementById("worker-name");
    const workerPhone = document.getElementById("worker-phone");

    const statCandidates = document.getElementById("stat-candidates");

    const resDuration = document.getElementById("res-duration");
    const resSamplerate = document.getElementById("res-samplerate");
    const resBitrate = document.getElementById("res-bitrate");
    const resLoudness = document.getElementById("res-loudness");
    const resSnr = document.getElementById("res-snr");
    const resQuality = document.getElementById("res-quality");
    const statusBanner = document.getElementById("status-banner");

    const submissionsTbody = document.getElementById("submissions-tbody");
    const searchSubmissions = document.getElementById("search-submissions");
    const btnRefreshGallery = document.getElementById("btn-refresh-gallery");

    let allSubmissions = [];

    // Set canvas dimensions
    function resizeCanvas() {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = canvas.parentElement.clientHeight;
    }
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    // Initial stats and gallery load
    fetchStats();
    fetchSubmissions();

    // -------------------------------------------------------------
    // Tab Navigation
    // -------------------------------------------------------------
    btnTabSubmit.addEventListener("click", () => {
        btnTabSubmit.classList.add("active");
        btnTabGallery.classList.remove("active");
        tabSubmit.classList.add("active");
        tabGallery.classList.remove("active");
    });

    btnTabGallery.addEventListener("click", () => {
        btnTabGallery.classList.add("active");
        btnTabSubmit.classList.remove("active");
        tabGallery.classList.add("active");
        tabSubmit.classList.remove("active");
        fetchSubmissions();
    });

    // -------------------------------------------------------------
    // Source Toggle (Record vs Upload)
    // -------------------------------------------------------------
    toggleRecord.addEventListener("click", () => {
        toggleRecord.classList.add("active");
        toggleUpload.classList.remove("active");
        recorderBox.classList.remove("hidden");
        uploadBox.classList.add("hidden");
        resizeCanvas();
    });

    toggleUpload.addEventListener("click", () => {
        toggleUpload.classList.add("active");
        toggleRecord.classList.remove("active");
        uploadBox.classList.remove("hidden");
        recorderBox.classList.add("hidden");
    });

    // -------------------------------------------------------------
    // Waveform Visualizer (Monochrome Clean Line)
    // -------------------------------------------------------------
    function drawVisualizer() {
        if (!analyser) return;
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        function renderFrame() {
            animationId = requestAnimationFrame(renderFrame);
            analyser.getByteTimeDomainData(dataArray);

            canvasCtx.fillStyle = "#000000";
            canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

            canvasCtx.lineWidth = 1.5;
            canvasCtx.strokeStyle = "#ffffff";
            canvasCtx.beginPath();

            const sliceWidth = (canvas.width * 1.0) / bufferLength;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const v = dataArray[i] / 128.0;
                const y = (v * canvas.height) / 2;

                if (i === 0) {
                    canvasCtx.moveTo(x, y);
                } else {
                    canvasCtx.lineTo(x, y);
                }
                x += sliceWidth;
            }

            canvasCtx.lineTo(canvas.width, canvas.height / 2);
            canvasCtx.stroke();
        }
        renderFrame();
    }

    // -------------------------------------------------------------
    // Microphone Recording Flow
    // -------------------------------------------------------------
    btnStartRecord.addEventListener("click", async () => {
        try {
            audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioCtx.createMediaStreamSource(audioStream);
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = 2048;
            source.connect(analyser);

            audioChunks = [];
            mediaRecorder = new MediaRecorder(audioStream);

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };

            mediaRecorder.onstop = () => {
                recordedBlob = new Blob(audioChunks, { type: "audio/webm" });
                selectedFile = new File([recordedBlob], `recording_${Date.now()}.webm`, { type: "audio/webm" });
                setAudioPreview(URL.createObjectURL(recordedBlob));
            };

            mediaRecorder.start();
            recordingStartTime = Date.now();
            timerInterval = setInterval(updateTimer, 500);

            btnStartRecord.disabled = true;
            btnStopRecord.disabled = false;
            drawVisualizer();
        } catch (err) {
            alert("Microphone access denied: " + err.message);
        }
    });

    btnStopRecord.addEventListener("click", () => {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
        }
        if (audioStream) {
            audioStream.getTracks().forEach((track) => track.stop());
        }
        if (audioCtx) {
            audioCtx.close();
        }
        if (animationId) {
            cancelAnimationFrame(animationId);
        }
        clearInterval(timerInterval);
        recTimer.textContent = "00:00";

        btnStartRecord.disabled = false;
        btnStopRecord.disabled = true;
    });

    function updateTimer() {
        const diff = Math.floor((Date.now() - recordingStartTime) / 1000);
        const m = String(Math.floor(diff / 60)).padStart(2, "0");
        const s = String(diff % 60).padStart(2, "0");
        recTimer.textContent = `${m}:${s}`;
    }

    // -------------------------------------------------------------
    // File Drag & Drop / Browse Flow
    // -------------------------------------------------------------
    dropZone.addEventListener("click", () => fileInput.click());

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    function handleFileSelect(file) {
        selectedFile = file;
        recordedBlob = null;
        setAudioPreview(URL.createObjectURL(file));
    }

    function setAudioPreview(url) {
        previewPlayer.src = url;
        previewBox.classList.remove("hidden");
        checkFormValidity();
    }

    btnClearAudio.addEventListener("click", () => {
        previewPlayer.pause();
        previewPlayer.src = "";
        previewBox.classList.add("hidden");
        selectedFile = null;
        recordedBlob = null;
        fileInput.value = "";
        checkFormValidity();
    });

    workerName.addEventListener("input", checkFormValidity);
    workerPhone.addEventListener("input", checkFormValidity);

    function checkFormValidity() {
        const hasName = workerName.value.trim().length > 1;
        const hasPhone = workerPhone.value.trim().length >= 8;
        const hasAudio = selectedFile !== null;
        btnSubmit.disabled = !(hasName && hasPhone && hasAudio);
    }

    // -------------------------------------------------------------
    // Submission Flow
    // -------------------------------------------------------------
    btnSubmit.addEventListener("click", async () => {
        if (!selectedFile) return;

        btnSubmit.disabled = true;
        btnSubmit.textContent = "Processing & Extracting...";
        statusBanner.className = "status-indicator";
        statusBanner.textContent = "Extracting acoustic parameters and persisting candidate record...";

        const formData = new FormData();
        formData.append("name", workerName.value.trim());
        formData.append("phone", workerPhone.value.trim());
        formData.append("audio_file", selectedFile);

        try {
            const resp = await fetch("/api/audio/submit", {
                method: "POST",
                body: formData,
            });

            const result = await resp.json();

            if (!resp.ok) {
                throw new Error(result.detail || "Submission failed");
            }

            const sub = result.submission;
            resDuration.textContent = `${sub.duration_seconds}s`;
            resSamplerate.textContent = `${sub.sample_rate_khz} kHz`;
            resBitrate.textContent = `${sub.bitrate_kbps} kbps`;
            resLoudness.textContent = `${sub.loudness_dbfs} dBFS`;
            resSnr.textContent = `${sub.snr_db ?? "—"} dB`;
            resQuality.textContent = sub.quality_grade;

            statusBanner.className = "status-indicator success";
            statusBanner.textContent = `Submission verified: Record stored for ${sub.candidate_name} (${sub.candidate_phone}).`;

            workerName.value = "";
            workerPhone.value = "";
            btnClearAudio.click();
            fetchStats();
            fetchSubmissions();
        } catch (err) {
            statusBanner.className = "status-indicator error";
            statusBanner.textContent = `Error: ${err.message}`;
        } finally {
            btnSubmit.textContent = "Submit & Extract Properties";
            checkFormValidity();
        }
    });

    // -------------------------------------------------------------
    // Stats & History Flow
    // -------------------------------------------------------------
    async function fetchStats() {
        try {
            const resp = await fetch("/api/stats");
            const data = await resp.json();
            statCandidates.textContent = data.total_candidates ?? "--";
        } catch (e) {
            console.error("Stats error:", e);
        }
    }

    async function fetchSubmissions() {
        try {
            const resp = await fetch("/api/audio/submissions");
            allSubmissions = await resp.json();
            renderGallery(allSubmissions);
        } catch (e) {
            submissionsTbody.innerHTML = `<tr><td colspan="10" class="text-center">Error loading history.</td></tr>`;
        }
    }

    btnRefreshGallery.addEventListener("click", fetchSubmissions);

    searchSubmissions.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase().trim();
        const filtered = allSubmissions.filter(
            (s) =>
                s.candidate_name.toLowerCase().includes(query) ||
                s.candidate_phone.includes(query)
        );
        renderGallery(filtered);
    });

    function renderGallery(submissions) {
        if (!submissions || submissions.length === 0) {
            submissionsTbody.innerHTML = `<tr><td colspan="10" class="text-center" style="color: var(--text-muted);">No submissions recorded yet.</td></tr>`;
            return;
        }

        submissionsTbody.innerHTML = submissions
            .map(
                (s) => `
            <tr>
                <td><strong>${escapeHtml(s.candidate_name)}</strong></td>
                <td><span class="code-badge">${escapeHtml(s.candidate_phone)}</span></td>
                <td>
                    <audio controls preload="none" class="custom-audio" style="height: 30px; width: 170px;">
                        <source src="/api/audio/file/${encodeURIComponent(s.file_name)}" type="audio/wav">
                    </audio>
                </td>
                <td>${s.duration_seconds}s</td>
                <td>${s.sample_rate_khz} kHz</td>
                <td>${s.bitrate_kbps} kbps</td>
                <td>${s.loudness_dbfs} dBFS</td>
                <td>${s.snr_db ?? "—"} dB</td>
                <td>${escapeHtml(s.quality_grade)}</td>
                <td style="color: var(--text-muted); font-size: 11px;">${s.created_at || "Recent"}</td>
            </tr>
        `
            )
            .join("");
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
