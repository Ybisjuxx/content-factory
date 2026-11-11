import { gsap } from "gsap/dist/gsap.js";
import { useGSAP } from "@gsap/react/dist/index.js";

import { CustomEase } from "gsap/dist/CustomEase.js";
import { CustomBounce } from "gsap/dist/CustomBounce.js";
import { CustomWiggle } from "gsap/dist/CustomWiggle.js";
import { RoughEase, ExpoScaleEase, SlowMo } from "gsap/dist/EasePack.js";

import { Draggable } from "gsap/dist/Draggable.js";
import { DrawSVGPlugin } from "gsap/dist/DrawSVGPlugin.js";
import { EaselPlugin } from "gsap/dist/EaselPlugin.js";
import { Flip } from "gsap/dist/Flip.js";
import { GSDevTools } from "gsap/dist/GSDevTools.js";
import { InertiaPlugin } from "gsap/dist/InertiaPlugin.js";
import { MotionPathHelper } from "gsap/dist/MotionPathHelper.js";
import { MotionPathPlugin } from "gsap/dist/MotionPathPlugin.js";
import { MorphSVGPlugin } from "gsap/dist/MorphSVGPlugin.js";
import { Observer } from "gsap/dist/Observer.js";
import { Physics2DPlugin } from "gsap/dist/Physics2DPlugin.js";
import { PhysicsPropsPlugin } from "gsap/dist/PhysicsPropsPlugin.js";
import { PixiPlugin } from "gsap/dist/PixiPlugin.js";
import { ScrambleTextPlugin } from "gsap/dist/ScrambleTextPlugin.js";
import { ScrollTrigger } from "gsap/dist/ScrollTrigger.js";
import { ScrollSmoother } from "gsap/dist/ScrollSmoother.js";
import { ScrollToPlugin } from "gsap/dist/ScrollToPlugin.js";
import { SplitText } from "gsap/dist/SplitText.js";
import { TextPlugin } from "gsap/dist/TextPlugin.js";

gsap.registerPlugin(
  useGSAP,
  Draggable,
  DrawSVGPlugin,
  EaselPlugin,
  Flip,
  GSDevTools,
  InertiaPlugin,
  MotionPathHelper,
  MotionPathPlugin,
  MorphSVGPlugin,
  Observer,
  Physics2DPlugin,
  PhysicsPropsPlugin,
  PixiPlugin,
  ScrambleTextPlugin,
  ScrollTrigger,
  ScrollSmoother,
  ScrollToPlugin,
  SplitText,
  TextPlugin,
  RoughEase,
  ExpoScaleEase,
  SlowMo,
  CustomEase,
  CustomBounce,
  CustomWiggle
);

// High-performance GSAP utility helpers (from greensock/gsap-skills)
export const {
  clamp,
  mapRange,
  normalize,
  interpolate,
  random,
  snap,
  toArray,
  wrap,
  pipe,
  distribute
} = gsap.utils;

export const quickTo = gsap.quickTo.bind(gsap);
export const quickSetter = gsap.quickSetter.bind(gsap);
export const matchMedia = gsap.matchMedia.bind(gsap);

export {
  gsap,
  useGSAP,
  Draggable,
  DrawSVGPlugin,
  EaselPlugin,
  Flip,
  GSDevTools,
  InertiaPlugin,
  MotionPathHelper,
  MotionPathPlugin,
  MorphSVGPlugin,
  Observer,
  Physics2DPlugin,
  PhysicsPropsPlugin,
  PixiPlugin,
  ScrambleTextPlugin,
  ScrollTrigger,
  ScrollSmoother,
  ScrollToPlugin,
  SplitText,
  TextPlugin,
  RoughEase,
  ExpoScaleEase,
  SlowMo,
  CustomEase,
  CustomBounce,
  CustomWiggle
};

export default gsap;

