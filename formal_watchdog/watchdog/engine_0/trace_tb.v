`ifndef VERILATOR
module testbench;
  reg [4095:0] vcdfile;
  reg clock;
`else
module testbench(input clock, output reg genclock);
  initial genclock = 1;
`endif
  reg genclock = 1;
  reg [31:0] cycle = 0;
  watchdog_formal UUT (

  );
`ifndef VERILATOR
  initial begin
    if ($value$plusargs("vcd=%s", vcdfile)) begin
      $dumpfile(vcdfile);
      $dumpvars(0, testbench);
    end
    #5 clock = 0;
    while (genclock) begin
      #5 clock = 0;
      #5 clock = 1;
    end
  end
`endif
  initial begin
`ifndef VERILATOR
    #1;
`endif
    // UUT.$auto$async2sync.\cc:101:execute$107  = 1'b0;
    // UUT.$auto$async2sync.\cc:101:execute$113  = 1'b0;
    // UUT.$auto$async2sync.\cc:101:execute$119  = 1'b0;
    // UUT.$auto$async2sync.\cc:101:execute$125  = 1'b0;
    // UUT.$auto$async2sync.\cc:110:execute$105  = 1'b1;
    // UUT.$auto$async2sync.\cc:110:execute$111  = 1'b1;
    // UUT.$auto$async2sync.\cc:110:execute$117  = 1'b1;
    // UUT.$auto$async2sync.\cc:110:execute$123  = 1'b1;
    UUT._witness_.anyinit_procdff_86 = 1'b1;
    UUT._witness_.anyinit_procdff_87 = 2'b11;
    UUT._witness_.anyinit_procdff_88 = 1'b1;
    UUT._witness_.anyinit_procdff_89 = 1'b1;
    UUT._witness_.anyinit_procdff_90 = 2'b11;
    UUT._witness_.anyinit_procdff_91 = 1'b1;
    UUT._witness_.anyinit_procdff_92 = 1'b1;
    UUT._witness_.anyinit_procdff_93 = 2'b11;
    UUT._witness_.anyinit_procdff_94 = 1'b1;
    UUT.dut._witness_.anyinit_procdff_100 = 2'b11;
    UUT.f_past_valid = 1'b0;

    // state 0
  end
  always @(posedge clock) begin
    // state 1
    if (cycle == 0) begin
    end

    genclock <= cycle < 1;
    cycle <= cycle + 1;
  end
endmodule
