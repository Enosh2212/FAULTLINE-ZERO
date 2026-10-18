import {mountAsciiField} from './ascii_field.js';
import {mountTesseractPreview} from './tesseract-preview.js';
const canvas = document.getElementById('hero-ascii-canvas');
const root = document.getElementById('view-landing');
const section=canvas.closest('.landing-hero-section');
const preview=new URLSearchParams(location.search).get('hero-preview')==='tesseract';
if(!preview || !mountTesseractPreview(canvas,section,root)) {
  // A WebGL canvas cannot switch to 2D; use a fresh canvas for graceful fallback.
  const fallback=preview?canvas.cloneNode():canvas;
  if(preview)canvas.replaceWith(fallback);
  mountAsciiField(fallback,section,{root,isActive:()=>root.classList.contains('active')});
}