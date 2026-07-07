<template>
  <div class="cow-container" :class="status">
    <div class="cow">
      <!-- horns -->
      <div class="horn left"></div>
      <div class="horn right"></div>

      <!-- ears -->
      <div class="ear left"></div>
      <div class="ear right"></div>

      <!-- head -->
      <div class="head">
        <!-- spots -->
        <div class="spot s1"></div>
        <div class="spot s2"></div>
        <div class="spot s3"></div>

        <!-- eyes -->
        <div class="eyes">
          <div class="eye left">
            <div class="pupil"></div>
          </div>
          <div class="eye right">
            <div class="pupil"></div>
          </div>
        </div>

        <!-- snout -->
        <div class="snout">
          <div class="nostril left"></div>
          <div class="nostril right"></div>
          <!-- mouth -->
          <div class="mouth" :class="status"></div>
        </div>
      </div>

      <!-- status props -->
      <div class="sweat" v-if="status === 'working'">💦</div>
      <div class="spiral" v-if="status === 'blocked'">🌀</div>
      <div class="zzz" v-if="status === 'idle'">💤</div>
      <div class="stars" v-if="status === 'done'">✨</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  status: { type: String, default: 'idle' }
})
</script>

<style scoped>
.cow-container {
  display: flex;
  justify-content: center;
  align-items: center;
}

.cow {
  position: relative;
  width: 120px;
  height: 140px;
  display: flex;
  justify-content: center;
  align-items: flex-end;
}

/* ========== horns ========== */
.horn {
  position: absolute;
  top: 10px;
  width: 14px;
  height: 20px;
  background: #8B7355;
  border-radius: 7px 7px 3px 3px;
  z-index: 2;
}
.horn.left  { left: 28px; transform: rotate(-15deg); }
.horn.right { right: 28px; transform: rotate(15deg); }

/* ========== ears ========== */
.ear {
  position: absolute;
  top: 28px;
  width: 16px;
  height: 22px;
  background: #D4956A;
  border-radius: 50%;
  z-index: 1;
}
.ear.left  { left: 18px; transform: rotate(-20deg); }
.ear.right { right: 18px; transform: rotate(20deg); }

/* ========== head ========== */
.head {
  position: relative;
  width: 84px;
  height: 88px;
  background: #F5E6D0;
  border-radius: 45% 45% 40% 40%;
  z-index: 3;
}

/* ========== spots ========== */
.spot {
  position: absolute;
  background: #4A3728;
  border-radius: 50%;
  opacity: 0.3;
}
.s1 { width: 16px; height: 14px; top: 12px; left: 14px; }
.s2 { width: 12px; height: 10px; top: 16px; right: 18px; }
.s3 { width: 10px; height: 8px;  bottom: 42px; left: 50px; }

/* ========== eyes ========== */
.eyes {
  position: absolute;
  top: 28px;
  left: 0;
  width: 100%;
  display: flex;
  justify-content: space-around;
  padding: 0 16px;
}
.eye {
  width: 14px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  border: 2px solid #4A3728;
  position: relative;
  overflow: hidden;
}
.pupil {
  width: 8px;
  height: 10px;
  background: #2C1810;
  border-radius: 50%;
  position: relative;
  transition: all 0.3s ease;
}

/* eye expressions */
.cow-container.working .eye {
  height: 18px;
  border-color: #22c55e;
}
.cow-container.working .pupil {
  width: 6px;
  height: 6px;
  background: #22c55e;
  animation: blink 2s ease-in-out infinite;
}

.cow-container.blocked .eye {
  background: transparent;
  border: none;
  overflow: visible;
}
.cow-container.blocked .pupil {
  width: 4px;
  height: 16px;
  border-radius: 2px;
  background: #ef4444;
  transform: translate(4px, -2px) rotate(45deg);
  box-shadow: -4px 6px 0 #ef4444;
}

.cow-container.idle .pupil {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #4A3728;
  transform: translateY(6px);
}

.cow-container.done .pupil {
  background: #3b82f6;
  animation: bounce 1s ease-in-out infinite;
}

/* ========== snout ========== */
.snout {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  width: 36px;
  height: 22px;
  background: #E8C9A8;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.nostril {
  width: 5px;
  height: 5px;
  background: #8B7355;
  border-radius: 50%;
}

/* ========== mouth ========== */
.mouth {
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 18px;
  height: 10px;
  border-radius: 0 0 12px 12px;
  transition: all 0.3s ease;
}

/* idle: small smile */
.mouth.idle {
  width: 14px;
  height: 6px;
  border: 2px solid #4A3728;
  border-top: none;
  border-radius: 0 0 10px 10px;
}

/* working: open mouth + sweat */
.mouth.working {
  width: 16px;
  height: 12px;
  background: #4A3728;
  border-radius: 0 0 8px 8px;
}

/* blocked: wavy mouth */
.mouth.blocked {
  width: 20px;
  height: 8px;
  border: none;
  background: none;
}
.mouth.blocked::before {
  content: '~~~';
  font-size: 12px;
  letter-spacing: -2px;
  color: #ef4444;
  position: absolute;
  top: -2px;
  left: -4px;
}

/* done: big smile */
.mouth.done {
  width: 20px;
  height: 12px;
  border: 2px solid #3b82f6;
  border-top: none;
  border-radius: 0 0 14px 14px;
}

/* ========== props ========== */
.sweat, .spiral, .zzz, .stars {
  position: absolute;
  font-size: 18px;
  top: -6px;
  right: 4px;
  animation: float 2s ease-in-out infinite;
  z-index: 5;
}
.spiral { animation: spin 1s linear infinite; }
.zzz { top: -12px; right: -4px; font-size: 16px; }
.stars { top: -8px; right: 0; font-size: 14px; animation: sparkle 1.5s ease-in-out infinite; }

/* ========== animations ========== */
@keyframes blink {
  0%, 90%, 100% { height: 6px; }
  95% { height: 2px; }
}
@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes sparkle {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

/* ========== status animations on container ========== */
.cow-container.working {
  animation: cow-wobble 0.6s ease-in-out infinite;
}
.cow-container.blocked {
  animation: cow-shake 0.4s ease-in-out infinite;
}
.cow-container.idle {
  animation: cow-idle-breathe 3s ease-in-out infinite;
}
.cow-container.done {
  animation: cow-done-bounce 0.5s ease;
}

@keyframes cow-wobble {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-3px); }
  75% { transform: translateX(3px); }
}
@keyframes cow-shake {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(-3deg); }
  75% { transform: rotate(3deg); }
}
@keyframes cow-idle-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
}
@keyframes cow-done-bounce {
  0% { transform: scale(1); }
  30% { transform: scale(1.15); }
  60% { transform: scale(0.95); }
  100% { transform: scale(1); }
}
</style>
