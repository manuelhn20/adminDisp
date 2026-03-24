// Copiado desde static/parallax_cards/script.js

Vue.config.devtools = true;

Vue.component('card', {
  template: `
    <div class="card-wrap"
      @mousemove="handleMouseMove"
      @mouseenter="handleMouseEnter"
      @mouseleave="handleMouseLeave"
      @click="handleClick"
      ref="card"
      :style="{ cursor: dataRoute ? 'pointer' : 'default' }">
      <div class="card"
        :style="cardStyle">
        <div class="card-bg" :style="[cardBgTransform, cardBgImage]"></div>
        <div class="card-info">
          <slot name="header"></slot>
          <slot name="content"></slot>
        </div>
      </div>
    </div>`,
  mounted() {
    // Cache size for ratio calculations
    this.width = this.$refs.card.offsetWidth;
    this.height = this.$refs.card.offsetHeight;

    // Keep size updated (responsive)
    window.addEventListener('resize', this.handleResize, { passive: true });
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.handleResize);
  },
  props: ['dataImage', 'dataRoute'],
  data: () => ({
    width: 0,
    height: 0,
    mouseX: 0,
    mouseY: 0,
    mouseLeaveDelay: null
  }),
  computed: {
    mousePX() {
      return this.mouseX / this.width;
    },
    mousePY() {
      return this.mouseY / this.height;
    },
    cardStyle() {
      // Softer tilt
      const rX = this.mousePX * 18;
      const rY = this.mousePY * -18;
      return {
        transform: `rotateY(${rX}deg) rotateX(${rY}deg)`
      };
    },
    cardBgTransform() {
      // Slight parallax on background
      const tX = this.mousePX * -28;
      const tY = this.mousePY * -28;
      return {
        transform: `translateX(${tX}px) translateY(${tY}px)`
      }
    },
    cardBgImage() {
      return {
        backgroundImage: `url(${this.dataImage})`
      }
    }
  },
  methods: {
    handleMouseMove(e) {
      const rect = this.$refs.card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      this.mouseX = x - rect.width / 2;
      this.mouseY = y - rect.height / 2;

      this.width = rect.width;
      this.height = rect.height;
    },
    handleMouseEnter() {
      clearTimeout(this.mouseLeaveDelay);
    },
    handleMouseLeave() {
      this.mouseLeaveDelay = setTimeout(()=>{
        this.mouseX = 0;
        this.mouseY = 0;
      }, 1000);
    },
    handleResize() {
      if (!this.$refs.card) return;
      const rect = this.$refs.card.getBoundingClientRect();
      this.width = rect.width;
      this.height = rect.height;
    },
    handleClick() {
      if (this.dataRoute) {
        window.location.href = this.dataRoute;
      }
    },
  }
});

const app = new Vue({ el: '#app' });
