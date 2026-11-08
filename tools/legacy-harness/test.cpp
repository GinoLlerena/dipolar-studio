#include "src/stdafx.h"
#include "src/Matriz.h"
#include "src/SistEcuac.h"
#include <cstdio>
static void eig(const char* name,double xx,double yy,double zz,double xy,double xz,double yz){
  CMatriz m; m.EstableceOrdenMatriz(3);
  double a[4][4]={{0},{0,xx,xy,xz},{0,xy,yy,yz},{0,xz,yz,zz}};
  for(int i=1;i<=3;i++)for(int j=1;j<=3;j++)m.EstableceCoeficientes(i,j,a[i][j]);
  m.DiagonalizaMatriz();
  printf("%-34s -> Sxx=%9.5f Syy=%9.5f Szz=%9.5f\n",name,m.DevuelveValorPropio(1),m.DevuelveValorPropio(2),m.DevuelveValorPropio(3));
}
int main(){
  // traceless order matrices
  eig("diagonal (D4-like)",      -0.10,-0.20,0.30, 0,0,0);
  eig("D2: only Sxy!=0",          -0.10,-0.20,0.30, 0.05,0,0);   // expected approx -0.2207,-0.0793,0.3
  eig("only Sxz!=0",              -0.10,-0.20,0.30, 0,0.05,0);   // expected -0.2,-0.1050..,0.305
  eig("only Syz!=0",              -0.10,-0.20,0.30, 0,0,0.05);
  eig("general",                  -0.10,-0.20,0.30, 0.05,0.02,0.03);
  // SistEcuac: 3x3 where 1 eq has a single unknown (partial path)
  CSistEcuac s; s.EstableceCantVariab(3);
  double A[3][3]={{2,0,0},{1,3,1},{1,1,4}}; double x[3]={1,2,3}; double b[3];
  for(int i=0;i<3;i++){b[i]=0;for(int j=0;j<3;j++){s.EstableceCoeff(i,j,A[i][j]);b[i]+=A[i][j]*x[j];}}
  for(int i=0;i<3;i++) s.EstableceResultado(i,b[i]);
  s.ResuelveSistemaDeEcuaciones();
  printf("SistEcuac partial-path solve, expected x=(1,2,3): got (%g, %g, %g)\n",s.DevuelveResultado(0),s.DevuelveResultado(1),s.DevuelveResultado(2));
  CSistEcuac g; g.EstableceCantVariab(3);
  double B[3][3]={{2,1,1},{1,3,1},{1,1,4}};
  for(int i=0;i<3;i++){b[i]=0;for(int j=0;j<3;j++){g.EstableceCoeff(i,j,B[i][j]);b[i]+=B[i][j]*x[j];}}
  for(int i=0;i<3;i++) g.EstableceResultado(i,b[i]);
  g.ResuelveSistemaDeEcuaciones();
  printf("SistEcuac full Gauss solve,  expected x=(1,2,3): got (%g, %g, %g)\n",g.DevuelveResultado(0),g.DevuelveResultado(1),g.DevuelveResultado(2));
}
