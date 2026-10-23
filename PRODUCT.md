# Product

## Register

product

## Users

Teachers, exam proctors, and operators who need a fast way to review images, uploaded videos, or a local webcam feed during an exam setting. They work under time pressure and need evidence they can understand immediately, not a noisy analytics dashboard.

## Product Purpose

ExamGuard detects suspected cell phone usage in exam contexts using YOLO and OpenCV. The product should help operators upload an image, process a video, or watch a realtime camera feed, then inspect annotated evidence and alert state without breaking flow. Success means the interface feels trustworthy, stable, and clear enough to use during a real supervision session.

## Brand Personality

Tin cậy, sang, bình tĩnh. The tone is calm institutional confidence: serious about violations, careful about evidence, and restrained in visual expression.

## Anti-references

Do not look like a broken Streamlit app, nested iframe UI, wedding/floral landing page, cyberpunk dashboard, loud neon interface, or fake demo showcase. Avoid hard-to-read Vietnamese serif headings, heavy lime surfaces, decorative grids, random squiggles, cluttered fake metrics, and anything that makes the detection workflow feel less credible.

## Design Principles

1. Evidence before alarm: every alert should feel grounded in visible frame evidence, labels, confidence, and time.
2. Calm authority over spectacle: the UI can be cinematic and premium, but it should never distract from the supervision task.
3. One workflow, many sources: image, video, and camera should share the same detector vocabulary and interaction model.
4. Vietnamese-first clarity: typography, labels, states, and mobile layouts must handle Vietnamese text cleanly.
5. Fail safely: missing custom models, camera issues, upload errors, and notification problems should be explicit and non-destructive.

## Accessibility & Inclusion

Target clear contrast for body text and controls, keyboard-visible focus states, responsive layouts with no horizontal overflow, readable Vietnamese diacritics, and reduced-motion support through `prefers-reduced-motion`. Motion should support state and orientation, not block task completion.
