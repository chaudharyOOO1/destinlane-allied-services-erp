import React, { useRef, useState, useEffect, useCallback, useMemo } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Camera, RotateCcw, Check, Loader2, AlertCircle } from "lucide-react";
import { Capacitor } from "@capacitor/core";
import { Camera as NativeCamera, CameraDirection, CameraResultType, CameraSource } from "@capacitor/camera";

/** Draws a translucent stamp bar with the punch time, location name and GPS onto the photo. */
function drawStamp(canvas, lines) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  const pad = Math.round(w * 0.045);
  const fontSize = Math.round(w * 0.038);
  const lineH = Math.round(fontSize * 1.4);
  const boxH = lines.length * lineH + pad * 1.4;

  ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
  ctx.fillRect(0, h - boxH, w, boxH);

  ctx.fillStyle = "#ffffff";
  ctx.font = `600 ${fontSize}px ui-sans-serif, system-ui, sans-serif`;
  ctx.textBaseline = "top";
  lines.forEach((line, i) => {
    ctx.fillText(line, pad, h - boxH + pad * 0.7 + i * lineH, w - pad * 2);
  });
}

export default function SelfieCapture({ open, onOpenChange, onConfirm, busy, punchTime, coords, place }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [shot, setShot] = useState(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);

  const stampLines = useMemo(() => {
    const d = punchTime ? new Date(punchTime) : new Date();
    const lines = [
      `Punch In: ${d.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })}, ${d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true })}`,
      `Location: ${place || "Unavailable"}`,
    ];
    if (coords) {
      lines.push(
        `GPS: ${coords.lat.toFixed(5)}, ${coords.lng.toFixed(5)}${
          coords.accuracy ? `  (±${Math.round(coords.accuracy)}m)` : ""
        }`
      );
    }
    return lines;
  }, [punchTime, coords, place]);

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const startCamera = useCallback(async () => {
    setError("");
    setStarting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 640, height: 640 },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch {
      setError("Camera unavailable — allow camera access to take your punch selfie.");
    } finally {
      setStarting(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      setShot(null);
      startCamera();
    } else {
      stopStream();
    }
    return () => stopStream();
  }, [open, startCamera, stopStream]);

  const capture = async () => {
    if (Capacitor.isNativePlatform()) {
      try {
        setError("");
        setStarting(true);

        const photo = await NativeCamera.getPhoto({
          source: CameraSource.Camera,
          direction: CameraDirection.Front,
          resultType: CameraResultType.DataUrl,
          quality: 85,
          allowEditing: false,
        });

        if (!photo.dataUrl) {
          throw new Error("Camera did not return a photo.");
        }

        const image = new Image();
        image.onload = () => {
          const size = Math.min(image.naturalWidth, image.naturalHeight);
          const canvas = document.createElement("canvas");
          canvas.width = size;
          canvas.height = size;
          const ctx = canvas.getContext("2d");

          ctx.drawImage(
            image,
            (image.naturalWidth - size) / 2,
            (image.naturalHeight - size) / 2,
            size,
            size,
            0,
            0,
            size,
            size
          );

          drawStamp(canvas, stampLines);

          canvas.toBlob(
            (blob) => {
              if (blob) {
                setShot({
                  url: URL.createObjectURL(blob),
                  blob,
                });
              } else {
                setError("Could not prepare the captured photo.");
              }
            },
            "image/jpeg",
            0.85
          );
          setStarting(false);
        };

        image.onerror = () => {
          setStarting(false);
          setError("Could not read the captured photo.");
        };

        image.src = photo.dataUrl;
      } catch (err) {
        console.error("Native camera failed:", err);
        setStarting(false);
        setError(
          err?.message ||
            "Camera unavailable. Please allow camera access and try again."
        );
      }
      return;
    }

    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const size = Math.min(video.videoWidth, video.videoHeight);
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(
      video,
      (video.videoWidth - size) / 2,
      (video.videoHeight - size) / 2,
      size,
      size,
      0,
      0,
      size,
      size
    );
    drawStamp(canvas, stampLines);
    canvas.toBlob(
      (blob) => {
        if (blob) setShot({ url: URL.createObjectURL(blob), blob });
      },
      "image/jpeg",
      0.85
    );
    stopStream();
  };

  const retake = () => {
    if (shot) URL.revokeObjectURL(shot.url);
    setShot(null);
    startCamera();
  };

  const confirm = () => {
    if (!shot) return;
    const file = new File([shot.blob], `punch-${Date.now()}.jpg`, { type: "image/jpeg" });
    onConfirm(file);
  };

  const handleOpenChange = (next) => {
    if (!next) {
      if (shot) URL.revokeObjectURL(shot.url);
      setShot(null);
      stopStream();
    }
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Punch in selfie</DialogTitle>
          <DialogDescription>
            Your punch time, location name and GPS are stamped onto the photo.
          </DialogDescription>
        </DialogHeader>

        <div className="relative mx-auto aspect-square w-full max-w-xs overflow-hidden rounded-2xl bg-slate-900">
          {shot ? (
            <img src={shot.url} alt="Punch selfie preview" className="h-full w-full object-cover" />
          ) : (
            <video ref={videoRef} playsInline muted className="h-full w-full object-cover" />
          )}
          {starting && !shot && (
            <div className="absolute inset-0 flex items-center justify-center text-white/70">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          )}
        </div>

        {!shot && (
          <div className="rounded-xl bg-slate-50 px-3 py-2.5 text-xs text-slate-500">
            {stampLines.map((line) => (
              <p key={line} className="truncate font-medium text-slate-600">
                {line}
              </p>
            ))}
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2.5 text-xs text-amber-700 ring-1 ring-amber-100">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {shot ? (
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={retake} disabled={busy}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Retake
            </Button>
            <Button className="flex-1" onClick={confirm} disabled={busy}>
              {busy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Check className="mr-2 h-4 w-4" />
              )}
              Confirm Punch
            </Button>
          </div>
        ) : (
          <Button onClick={capture} disabled={starting || !!error} className="w-full">
            <Camera className="mr-2 h-4 w-4" />
            Capture Photo
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}