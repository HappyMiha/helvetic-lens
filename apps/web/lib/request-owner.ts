/** A response belongs to one mounted view and one captured authority epoch. */
export class RequestOwner {
  private generation = 0;
  private active = false;
  activate() {
    this.active = true;
  }
  deactivate() {
    this.active = false;
    this.generation++;
  }
  capture(authority: () => string) {
    const generation = this.generation;
    const identity = authority();
    return () =>
      this.active && generation === this.generation && identity === authority();
  }
}
