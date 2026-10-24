extern void unique(void);
extern void alpha_save(void);
extern void beta_save(void);
extern void external_missing(void);
void run(void (*unknown)(void), int flag) {
  unique();
  alpha_save();
  unknown();
  external_missing();
  void (*selected)(void) = flag ? alpha_save : beta_save;
  selected();
}
