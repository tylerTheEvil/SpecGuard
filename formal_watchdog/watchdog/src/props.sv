module watchdog_formal;
  reg clk;
  reg reset_n;
  reg error_flag;
  wire [1:0] state;

  localparam SAFE_STATE  = 2'b00;
  localparam RUN_STATE   = 2'b01;
  localparam ERROR_STATE = 2'b10;

  // DUT
  watchdog dut(
    .clk(clk),
    .reset_n(reset_n),
    .error_flag(error_flag),
    .state(state)
  );

  // constrain inputs to 0/1 (optional but nice)
  always @(*) begin
    assume(reset_n == 0 || reset_n == 1);
    assume(error_flag == 0 || error_flag == 1);
  end

  // Track past validity for $past usage
  reg f_past_valid;
  initial f_past_valid = 0;
  always @(posedge clk) f_past_valid <= 1;

  // Main assertions MUST be in a clocked block to use $past
  always @(posedge clk) begin
    // REQ-1: On reset, state must be SAFE_STATE (same cycle after edge)
    if (!reset_n) begin
      assert(state == SAFE_STATE);
    end

    if (f_past_valid) begin
      // REQ-2: SAFE -> RUN when no error (next cycle)
      if ($past(reset_n) && $past(state) == SAFE_STATE && !$past(error_flag))
        assert(state == RUN_STATE);

      // REQ-3: RUN -> ERROR when error_flag=1 (next cycle)
      if ($past(reset_n) && $past(state) == RUN_STATE && $past(error_flag))
        assert(state == ERROR_STATE);

      // REQ-4: ERROR -> SAFE when error_flag=0 (next cycle)
      if ($past(reset_n) && $past(state) == ERROR_STATE && !$past(error_flag))
        assert(state == SAFE_STATE);
    end

    // REQ-5: State encoding always valid
    assert(state == SAFE_STATE || state == RUN_STATE || state == ERROR_STATE);
  end

endmodule
