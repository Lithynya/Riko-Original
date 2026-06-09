import * as THREE from 'three';

export class AnimationManager {
  constructor(vrm, audioMgr, renderer, scene, camera, controls) {
    this.vrm        = vrm;
    this.audioMgr   = audioMgr;
    this.renderer   = renderer;
    this.scene      = scene;
    this.camera     = camera;
    this.controls   = controls;
    this.clock      = new THREE.Clock();
    this.isPlaying  = false;
    this.isVRMAPlaying = false; 
    this.isMixamoPlaying = false; 
    this.headTimer  = 0;
    this.nextHead   = 0;
    this.headTgt    = { x: 0, y: 0, z: 0 };
    this.headCur    = { x: 0, y: 0, z: 0 };

    this.bodyTimer  = 0;
    this.nextBody   = 0;
    this.bodyTgt    = { x: 0 };
    this.bodyCur    = { x: 0 };

    this.blinkTimer = 0;
    this.nextBlink  = 0;
    this.blinkVal   = 0;

    this.config = {
      // head motion range
      headNod: 0.2,
      headTurn: 0.13,
      headTilt: 0.15,

      // frequency and speed (idle vs talk)
      headFreqIdle: 1.8, headFreqTalk: 0.8,  // lower is faster
      headEaseIdle: 0.02, headEaseTalk: 0.04,

      // body motion
      sway: 0.1,
      swayFreqIdle: 2.8, swayFreqTalk: 1.8,
      swayEaseIdle: 0.01, swayEaseTalk: 0.02,

      // blink
      blinkMin: 0.5,
      blinkMax: 3.0,
      blinkSpeed: 8.0
    };

    // DON'T START THE ANIMATION LOOP HERE - LET THE MAIN LOOP HANDLE IT
    // this.animate();
  }

  // NEW: Method to set VRMA state
  setVRMAPlaying(isPlaying) {
    this.isVRMAPlaying = isPlaying;
  }

  // NEW: Method to set Mixamo state
  setMixamoPlaying(isPlaying) {
    this.isMixamoPlaying = isPlaying;
  }

  play() {
    this.audioMgr.resetMouth();
    this.audioMgr.audioElement.currentTime = 0;
    this.audioMgr.audioElement.play().catch(() => {});
    this.isPlaying = true;
  }

  stop() {
    this.audioMgr.audioElement.pause();
    this.isPlaying = false;
    this.audioMgr.resetMouth();
  }

  rand(min, max) {
    return min + Math.random() * (max - min);
  }

  getCurrentParams() {
    const talking = this.isPlaying && this.audioMgr.audioElement && !this.audioMgr.audioElement.ended;
    return {
      headFreq: talking ? this.config.headFreqTalk : this.config.headFreqIdle,
      headEase: talking ? this.config.headEaseTalk : this.config.headEaseIdle,
      swayFreq: talking ? this.config.swayFreqTalk : this.config.swayFreqIdle,
      swayEase: talking ? this.config.swayEaseTalk : this.config.swayEaseIdle
    };
  }

  // MODIFIED: Remove the animation loop, make this a simple update method
  update(deltaTime) {
    if (!this.vrm) return;

    // ALWAYS HANDLE BLINKING - regardless of VRMA/Mixamo state
    this.blinkTimer += deltaTime;
    if (this.blinkTimer > this.nextBlink) {
      this.blinkTimer = 0;
      this.nextBlink = this.rand(this.config.blinkMin, this.config.blinkMax);
    }
    this.blinkVal += (this.blinkTimer < 0.1 ? deltaTime : -deltaTime) * this.config.blinkSpeed;
    this.blinkVal = Math.max(0, Math.min(1, this.blinkVal));
    this.vrm.expressionManager.setValue('blink',   this.blinkVal);
    this.vrm.expressionManager.setValue('neutral', 1.0);

    // Handle audio/lip sync regardless of animation state
    if (this.isPlaying && this.audioMgr.audioElement) {
      this.audioMgr.updateLipSync(this.audioMgr.audioElement.currentTime);
      if (this.audioMgr.audioElement.ended) this.stop();
    }

    // SKIP IDLE ANIMATIONS IF VRMA IS PLAYING
    if (this.isVRMAPlaying) {
      return;
    }

    if (this.isMixamoPlaying) {
      return;
    }

    // *** enforce arms-down every frame (only when not playing VRMA) ***
    const leftArm  = this.vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
    const rightArm = this.vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
    leftArm.rotation.z  =  -1.2;
    rightArm.rotation.z = 1.2;

    const { headFreq, headEase, swayFreq, swayEase } = this.getCurrentParams();

    // head
    this.headTimer += deltaTime;
    if (this.headTimer > headFreq) {
      this.headTgt.x = this.rand(-this.config.headNod, this.config.headNod);
      this.headTgt.y = this.rand(-this.config.headTurn, this.config.headTurn);
      this.headTgt.z = this.rand(-this.config.headTilt, this.config.headTilt);
      this.headTimer = 0;
    }
    this.headCur.x += (this.headTgt.x - this.headCur.x) * headEase;
    this.headCur.y += (this.headTgt.y - this.headCur.y) * headEase;
    this.headCur.z += (this.headTgt.z - this.headCur.z) * headEase;
    const neck = this.vrm.humanoid.getNormalizedBoneNode('neck');
    neck.rotation.set(this.headCur.x, this.headCur.y, this.headCur.z);

    // body
    this.bodyTimer += deltaTime;
    if (this.bodyTimer > swayFreq) {
      this.bodyTgt.x = this.rand(-this.config.sway, this.config.sway);
      this.bodyTimer = 0;
    }
    this.bodyCur.x += (this.bodyTgt.x - this.bodyCur.x) * swayEase;
    const spine = this.vrm.humanoid.getNormalizedBoneNode('spine');
    spine.rotation.x = this.bodyCur.x;

    // DON'T CALL vrm.update() OR renderer.render() HERE - LET THE MAIN LOOP HANDLE IT
  }
}